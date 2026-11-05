"""Published asset aliases must bind exact released bytes and explicit history."""
import hashlib
import json
from pathlib import Path
import pytest
from evaluation.workflow import assets
from evaluation.workflow.expressions import operand
from evaluation.workflow.values import MissingEvidence


@pytest.fixture
def published(tmp_path, monkeypatch):
    folder = tmp_path / 'tasks/full/assets'
    folder.mkdir(parents=True)
    file = folder / 'coordinates.pdb'
    file.write_bytes(b'controlled coordinates\n')
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    (tmp_path / 'tasks/full/asset_manifest.json').write_text(
        json.dumps({'files': {file.name: {'sha256': digest}}}))
    monkeypatch.setattr(assets, 'ROOT', tmp_path)
    return file, digest


def test_exact_release_and_reviewed_history_only(published):
    file, digest = published
    result = operand({'operation': 'public_asset_paths', 'args': [
        {'value': file.name}, {'value': digest}, {'value': ['/old/coordinates.pdb']}]}, {})
    assert str(file) in result and 'asset://coordinates.pdb' in result
    assert '/old/coordinates.pdb' in result
    assert '/unrelated/coordinates.pdb' not in result


def test_same_name_changed_bytes_are_rejected(published):
    file, digest = published
    file.write_bytes(b'different structure\n')
    with pytest.raises(MissingEvidence):
        assets.public_asset_paths(file.name, digest, [])


def test_manifest_cannot_substitute_a_different_digest(published):
    file, digest = published
    with pytest.raises(MissingEvidence):
        assets.public_asset_paths(file.name, '0' * 64, [])


@pytest.mark.parametrize('name', ['../coordinates.pdb', '/coordinates.pdb', '..', '', 'a\\b'])
def test_invalid_names_are_rejected(published, name):
    with pytest.raises(MissingEvidence):
        assets.public_asset_paths(name, published[1], [])


def test_relocated_full_keeps_only_exact_previous_path(published):
    file, digest = published
    result = assets.public_asset_paths(file.name, digest, [])
    assert 'tasks/assets/coordinates.pdb' in result
    assert str(file.parents[3]/'tasks/assets/coordinates.pdb') in result
    assert '/unrelated/coordinates.pdb' not in result
