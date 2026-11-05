"""Hidden credential input and atomic updates preserve unrelated local services."""

import io
import stat
from unittest.mock import patch
import pytest
from dotenv import dotenv_values
from scripts.services.configure_api import hidden_key, save_settings


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
