# tests/test_meta_file_storage_singleton.py

import json
import os
from re import S
from unittest.mock import patch
from gcl_sdk.agents.universal.drivers.meta import MetaFileStorageSingleton


def test_storage_singleton_get_instance(tmp_path):
    meta_file = tmp_path / "test_meta.json"

    instance1 = MetaFileStorageSingleton(meta_file)
    instance2 = MetaFileStorageSingleton(meta_file)

    assert instance1 is instance2
    assert isinstance(instance1, MetaFileStorageSingleton)


def test_storage_singleton_get_instance_different(tmp_path):
    meta_file = tmp_path / "test_meta.json"
    meta_file2 = tmp_path / "test_meta2.json"

    instance1 = MetaFileStorageSingleton(meta_file)
    instance2 = MetaFileStorageSingleton(meta_file2)

    assert instance1 is not instance2
    assert isinstance(instance1, MetaFileStorageSingleton)


def test_storage_singleton_load_non_existent_file(tmp_path):
    meta_file = tmp_path / "non_existent.json"

    with patch("os.path.exists", return_value=False):
        storage = MetaFileStorageSingleton(meta_file)
        storage.load()

    assert storage == {}


def test_storage_singleton_load_existing_file(tmp_path):
    meta_file = tmp_path / "existing_meta.json"
    expected_data = {"key": "value"}

    with open(meta_file, "w") as f:
        json.dump(expected_data, f)

    storage = MetaFileStorageSingleton(meta_file)
    storage.load()

    assert storage == expected_data


def test_storage_singleton_persist(tmp_path):
    meta_file = tmp_path / "test_persist.json"
    new_vals = {"key": "new_val"}

    with patch("os.makedirs") as mock_makedirs:
        storage = MetaFileStorageSingleton(meta_file)
        storage.update(new_vals)
        storage.persist()

    with open(meta_file) as f:
        data = json.load(f)

    assert data == new_vals
    mock_makedirs.assert_called_once_with(
        os.path.dirname(meta_file), exist_ok=True
    )


def test_storage_singleton_persist_overwrite(tmp_path):
    meta_file = tmp_path / "test_persist.json"
    new_vals = {"key": "new_val"}

    storage = MetaFileStorageSingleton(meta_file)
    storage.update(new_vals)
    storage.persist()

    with open(meta_file) as f:
        data = json.load(f)

    assert data == new_vals

    new_data = {"key": "bad_value"}
    with open(meta_file, "w") as f:
        json.dump(new_data, f)

    storage.load()

    assert storage == new_data
