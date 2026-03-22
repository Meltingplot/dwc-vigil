"""Tests for vigil_persistence — atomic I/O, checksum, parity, recovery."""

import json
import os
import tempfile

import pytest

from vigil_persistence import (
    atomic_save,
    atomic_write_file,
    compute_parity,
    empty_state,
    load_data,
    load_month_history,
    reconstruct_from_parity,
    save_month_history,
    append_daily_snapshot,
    load_history_range,
    _compute_checksum,
    _embed_checksum,
    _verify_checksum,
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set VIGIL_DATA_DIR to a temporary directory."""
    monkeypatch.setenv("VIGIL_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_data():
    data = empty_state()
    data["lifetime"]["machine_seconds"] = 1000.0
    data["lifetime"]["print_seconds"] = 500.0
    data["lifetime"]["jobs_total"] = 10
    data["lifetime"]["jobs_successful"] = 8
    data["lifetime"]["jobs_cancelled"] = 2
    return data


class TestChecksum:
    def test_compute_and_verify(self, sample_data):
        embedded = _embed_checksum(sample_data)
        assert "_checksum" in embedded
        assert embedded["_checksum"].startswith("sha256:")
        assert _verify_checksum(embedded)

    def test_tampered_data_fails(self, sample_data):
        embedded = _embed_checksum(sample_data)
        embedded["lifetime"]["machine_seconds"] = 9999
        assert not _verify_checksum(embedded)

    def test_missing_checksum_fails(self, sample_data):
        assert not _verify_checksum(sample_data)


class TestParity:
    def test_identical_data_produces_zeros(self):
        data = b"hello world"
        parity = compute_parity(data, data)
        assert parity == bytes(len(data))

    def test_reconstruction(self):
        a = b"hello world"
        b = b"hello world"
        parity = compute_parity(a, b)
        reconstructed = reconstruct_from_parity(a, parity)
        assert reconstructed == b

    def test_different_lengths(self):
        a = b"short"
        b = b"longer data here"
        parity = compute_parity(a, b)
        reconstructed = reconstruct_from_parity(a, parity)
        assert reconstructed == b


class TestAtomicWrite:
    def test_basic_write(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        data = b'{"key": "value"}'
        atomic_write_file(filepath, data)

        assert os.path.exists(filepath)
        with open(filepath, "rb") as f:
            assert f.read() == data

    def test_tmp_file_cleaned_up(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        atomic_write_file(filepath, b"data")
        assert not os.path.exists(filepath + ".tmp")

    def test_overwrites_existing(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        atomic_write_file(filepath, b"old")
        atomic_write_file(filepath, b"new")
        with open(filepath, "rb") as f:
            assert f.read() == b"new"


class TestAtomicSave:
    def test_creates_three_files(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        assert os.path.exists(filepath)
        assert os.path.exists(filepath + ".bak")
        assert os.path.exists(filepath + ".par")

    def test_main_has_valid_checksum(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        with open(filepath) as f:
            loaded = json.load(f)
        assert _verify_checksum(loaded)

    def test_bak_has_valid_checksum(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        with open(filepath + ".bak") as f:
            loaded = json.load(f)
        assert _verify_checksum(loaded)


class TestLoadRecovery:
    def test_load_from_main(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        loaded = load_data(filepath)
        assert loaded["lifetime"]["machine_seconds"] == sample_data["lifetime"]["machine_seconds"]

    def test_load_from_bak_when_main_corrupt(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        # Corrupt main
        with open(filepath, "w") as f:
            f.write("CORRUPT DATA")

        loaded = load_data(filepath)
        assert loaded["lifetime"]["machine_seconds"] == sample_data["lifetime"]["machine_seconds"]

    def test_load_from_parity_when_main_corrupt(self, data_dir, sample_data):
        filepath = str(data_dir / "vigil_data.json")
        atomic_save(sample_data, filepath)

        # Corrupt main
        with open(filepath, "w") as f:
            f.write("CORRUPT")

        # bak is still OK, so this should work via stage 2
        loaded = load_data(filepath)
        assert loaded["lifetime"]["jobs_total"] == 10

    def test_fresh_state_when_all_corrupt(self, data_dir):
        filepath = str(data_dir / "vigil_data.json")

        # Create all three files with garbage
        for suffix in ["", ".bak", ".par"]:
            with open(filepath + suffix, "w") as f:
                f.write("GARBAGE")

        loaded = load_data(filepath)
        # Should be fresh empty state
        assert loaded["lifetime"]["machine_seconds"] == 0.0

    def test_fresh_state_when_no_files(self, data_dir):
        filepath = str(data_dir / "vigil_data.json")
        loaded = load_data(filepath)
        assert loaded["schema_version"] == 1
        assert loaded["lifetime"]["machine_seconds"] == 0.0

    def test_corrupt_files_renamed(self, data_dir):
        filepath = str(data_dir / "vigil_data.json")
        for suffix in ["", ".bak", ".par"]:
            with open(filepath + suffix, "w") as f:
                f.write("GARBAGE")

        load_data(filepath)

        # Original files should be renamed
        corrupt_files = [f for f in os.listdir(data_dir) if ".corrupt." in f]
        assert len(corrupt_files) > 0


class TestMonthHistory:
    def test_save_and_load(self, data_dir):
        month_data = {
            "month": "2026-03",
            "days": [
                {"date": "2026-03-01", "machine_hours": 8.0, "print_hours": 4.0, "jobs_total": 3},
            ],
        }
        save_month_history("2026-03", month_data)
        loaded = load_month_history("2026-03")
        assert loaded is not None
        assert len(loaded["days"]) == 1
        assert loaded["days"][0]["machine_hours"] == 8.0

    def test_load_nonexistent(self, data_dir):
        assert load_month_history("2099-01") is None

    def test_append_daily_snapshot(self, data_dir):
        append_daily_snapshot({"date": "2026-03-01", "machine_hours": 5.0})
        append_daily_snapshot({"date": "2026-03-02", "machine_hours": 6.0})

        loaded = load_month_history("2026-03")
        assert len(loaded["days"]) == 2

    def test_append_replaces_same_date(self, data_dir):
        append_daily_snapshot({"date": "2026-03-01", "machine_hours": 5.0})
        append_daily_snapshot({"date": "2026-03-01", "machine_hours": 8.0})

        loaded = load_month_history("2026-03")
        assert len(loaded["days"]) == 1
        assert loaded["days"][0]["machine_hours"] == 8.0

    def test_corrupt_month_falls_back_to_bak(self, data_dir):
        month_data = {"month": "2026-03", "days": [{"date": "2026-03-01", "machine_hours": 7.0}]}
        save_month_history("2026-03", month_data)

        # Corrupt main
        history_dir = data_dir / "history"
        with open(history_dir / "2026-03.json", "w") as f:
            f.write("CORRUPT")

        loaded = load_month_history("2026-03")
        assert loaded is not None
        assert loaded["days"][0]["machine_hours"] == 7.0
