"""Hidden credential input and atomic updates preserve unrelated local services."""

import io
import stat
from unittest.mock import patch
import pytest
from dotenv import dotenv_values
from scripts.services.configure_api import hidden_key, save_settings, use_profile


def test_updates_preserve_other_services_and_roundtrip_key(tmp_path):
    path = tmp_path / "credentials/services.env"
    path.parent.mkdir()
    path.write_text(
        "# keep comment\nSCITOOL_EMBEDDING_API_KEY=embedding-test\nOTHER_SERVICE=keep\nSCITOOLFLOW_API_MODEL=old\n"
    )
    value = "test-key-with'quote\\slash"
    save_settings(path, {"SCITOOLFLOW_API_MODEL": "new", "SCITOOLFLOW_API_KEY": value})
    config = dotenv_values(path)
    assert config["SCITOOL_EMBEDDING_API_KEY"] == "embedding-test"
    assert config["OTHER_SERVICE"] == "keep"
    assert config["SCITOOLFLOW_API_MODEL"] == "new"
    assert config["SCITOOLFLOW_API_KEY"] == value
    assert "# keep comment" in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(path.parent.glob(".api-*"))


def test_symlink_is_not_replaced_or_written(tmp_path):
    target = tmp_path / "target"
    target.write_text("keep")
    path = tmp_path / "services.env"
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        save_settings(path, {"SCITOOLFLOW_API_KEY": "test"})
    assert target.read_text() == "keep" and path.is_symlink()


def test_failure_preserves_original_file_and_removes_staging_file(tmp_path):
    path = tmp_path / "services.env"
    path.write_text("OTHER_SERVICE=keep\n")
    with patch("scripts.services.configure_api.set_key", side_effect=OSError("test")):
        with pytest.raises(OSError):
            save_settings(path, {"SCITOOLFLOW_API_KEY": "test"})
    assert path.read_text() == "OTHER_SERVICE=keep\n"
    assert not list(path.parent.glob(".api-*"))


def test_redirected_input_never_uses_echo_fallback():
    with (
        patch("sys.stdin", io.StringIO("not-a-real-key")),
        patch("getpass.getpass") as prompt,
    ):
        with pytest.raises(ValueError, match="interactive terminal"):
            hidden_key()
    prompt.assert_not_called()


def test_saved_profiles_switch_endpoint_and_matching_key_together(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.services.configure_api.project_root", lambda: tmp_path)
    folder = tmp_path / ".local/credentials"
    save_settings(folder / "services.env", {"SCITOOL_EMBEDDING_API_KEY": "keep-embedding"})
    for name in ("official", "school"):
        save_settings(folder / "api" / (name + ".env"), {
            "SCITOOLFLOW_API_BASE": "https://" + name + ".example/v1",
            "SCITOOLFLOW_API_MODEL": name + "-model",
            "SCITOOLFLOW_API_KEY": name + "-test-key",
            "SCITOOLFLOW_API_EXTRA_BODY": "{}",
        })
    for name in ("school", "official"):
        use_profile(name)
        config = dotenv_values(folder / "services.env")
        assert config["SCITOOLFLOW_API_PROFILE"] == name
        assert config["SCITOOLFLOW_API_BASE"] == "https://" + name + ".example/v1"
        assert config["SCITOOLFLOW_API_KEY"] == name + "-test-key"
        assert config["SCITOOL_EMBEDDING_API_KEY"] == "keep-embedding"
        assert stat.S_IMODE((folder / "services.env").stat().st_mode) == 0o600


@pytest.mark.parametrize("name", ["../services", "bad/name", "", "/tmp/key"])
def test_saved_profile_name_cannot_escape_credentials_directory(name):
    with pytest.raises(ValueError, match="name is invalid"):
        use_profile(name)
