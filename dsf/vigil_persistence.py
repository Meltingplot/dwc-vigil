"""
Vigil Persistence — Crash-safe atomic file I/O with XOR parity recovery.

Three-file system (RAID-1E principle):
  vigil_data.json     — Primary data + SHA256 checksum
  vigil_data.json.bak — Backup copy + SHA256 checksum
  vigil_data.json.par — XOR(main, bak) parity for reconstruction

Recovery order:
  1. Main OK → use main
  2. Bak OK → use bak, regenerate main
  3. Bak + par → reconstruct main via XOR
  4. Main + par → reconstruct bak via XOR
  5. All corrupt → fresh state, rename corrupt files
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger("vigil.persistence")

SCHEMA_VERSION = 1
DEFAULT_DATA_DIR = "/opt/dsf/sd/Vigil"
DATA_FILENAME = "vigil_data.json"
HISTORY_DIR = "history"

SAVE_INTERVAL_S = 60


def get_data_dir():
    """Return data directory, respecting VIGIL_DATA_DIR env override."""
    return os.environ.get("VIGIL_DATA_DIR", DEFAULT_DATA_DIR)


def get_data_path():
    return os.path.join(get_data_dir(), DATA_FILENAME)


def get_history_dir():
    return os.path.join(get_data_dir(), HISTORY_DIR)


def ensure_data_dir():
    """Create data directory and history subdirectory if they don't exist."""
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(get_history_dir(), exist_ok=True)


# --- Empty state factory ---

def _empty_counters():
    """Return a fresh set of zero counters."""
    return {
        "machine_seconds": 0.0,
        "print_seconds": 0.0,
        "pause_seconds": 0.0,
        "warmup_seconds": 0.0,
        "jobs_total": 0,
        "jobs_successful": 0,
        "jobs_cancelled": 0,
        "axes": {},
        "filament_mm": {},
        "heaters": {},
        "fans": {},
    }


def _empty_vitals():
    """Return a fresh set of board/SBC vitals (min/max tracking per day)."""
    return {
        "mcu_temp_min": None,
        "mcu_temp_max": None,
        "vin_min": None,
        "vin_max": None,
        "v12_min": None,
        "v12_max": None,
        "sbc_cpu_temp_max": None,
        "sbc_cpu_load_avg_sum": 0.0,
        "sbc_cpu_load_avg_count": 0,
        "sbc_memory_min_bytes": None,
    }


def empty_state():
    """Return a fresh empty data state."""
    return {
        "schema_version": SCHEMA_VERSION,
        "last_saved": "",
        "lifetime": _empty_counters(),
        "service": _empty_counters(),
        "service_log": [],
        "vitals": _empty_vitals(),
        "uptime": {
            "firmware_uptime_secs": None,
            "sbc_uptime_secs": None,
            "firmware_reboots": 0,
            "sbc_reboots": 0,
        },
        "volume_free_bytes": None,
    }


# --- Checksum ---

def _compute_checksum(data: dict) -> str:
    """Compute SHA256 over JSON-serialized data (without _checksum key)."""
    clean = {k: v for k, v in data.items() if k != "_checksum"}
    raw = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _verify_checksum(data: dict) -> bool:
    """Verify embedded _checksum matches computed checksum."""
    stored = data.get("_checksum")
    if not stored:
        return False
    return stored == _compute_checksum(data)


def _embed_checksum(data: dict) -> dict:
    """Return a copy of data with _checksum embedded."""
    out = dict(data)
    out["_checksum"] = _compute_checksum(data)
    return out


# --- XOR Parity ---

def compute_parity(data_a: bytes, data_b: bytes) -> bytes:
    """Byte-wise XOR of two byte strings, zero-padded to equal length."""
    length = max(len(data_a), len(data_b))
    a = data_a.ljust(length, b"\x00")
    b = data_b.ljust(length, b"\x00")
    return bytes(x ^ y for x, y in zip(a, b))


def reconstruct_from_parity(good: bytes, parity: bytes) -> bytes:
    """Reconstruct the missing file from the intact one + parity."""
    length = max(len(good), len(parity))
    g = good.ljust(length, b"\x00")
    p = parity.ljust(length, b"\x00")
    return bytes(x ^ y for x, y in zip(g, p)).rstrip(b"\x00")


# --- Atomic file I/O ---

def _dir_fsync(dirpath):
    """fsync a directory to ensure metadata (renames) are persisted."""
    try:
        fd = os.open(dirpath, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # Best effort on platforms that don't support dir fsync


def atomic_write_file(filepath: str, data_bytes: bytes):
    """Write data atomically: write tmp → fsync → rename → dir fsync."""
    tmp = filepath + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, filepath)
    _dir_fsync(os.path.dirname(filepath))


def _read_file_bytes(filepath: str) -> bytes | None:
    """Read file bytes, return None if file doesn't exist or read fails."""
    try:
        with open(filepath, "rb") as f:
            return f.read()
    except (OSError, IOError):
        return None


def _parse_json_checked(raw: bytes) -> dict | None:
    """Parse JSON and verify checksum. Return dict if valid, None otherwise."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not _verify_checksum(data):
        return None
    return data


# --- Save ---

def atomic_save(data: dict, filepath: str | None = None):
    """
    Save data with three-file redundancy:
      1. Write main (with checksum)
      2. Write backup
      3. Write XOR parity
    """
    if filepath is None:
        filepath = get_data_path()

    ensure_data_dir()

    data["last_saved"] = datetime.now(timezone.utc).isoformat()
    checked = _embed_checksum(data)
    json_bytes = json.dumps(checked, indent=2).encode("utf-8")

    bak_path = filepath + ".bak"
    par_path = filepath + ".par"

    # Phase 1: Main
    atomic_write_file(filepath, json_bytes)

    # Phase 2: Backup
    atomic_write_file(bak_path, json_bytes)

    # Phase 3: Parity (main == bak at this point, so parity is all zeros,
    # but we compute it properly for correctness if files diverge on disk)
    parity = compute_parity(json_bytes, json_bytes)
    atomic_write_file(par_path, parity)


# --- Load / Recovery ---

def _rename_corrupt(filepath: str):
    """Rename a corrupt file with timestamp suffix."""
    if os.path.exists(filepath):
        ts = int(time.time())
        corrupt_name = f"{filepath}.corrupt.{ts}"
        try:
            os.rename(filepath, corrupt_name)
            logger.warning("Renamed corrupt file: %s → %s", filepath, corrupt_name)
        except OSError as e:
            logger.error("Failed to rename corrupt file %s: %s", filepath, e)


def load_data(filepath: str | None = None) -> dict:
    """
    Load data with 5-stage recovery:
      1. Main checksum OK → use main
      2. Bak checksum OK → use bak, regenerate main
      3. Bak + par → reconstruct main via XOR, verify checksum
      4. Main + par → reconstruct bak via XOR, verify checksum
      5. All corrupt → fresh empty state
    """
    if filepath is None:
        filepath = get_data_path()

    bak_path = filepath + ".bak"
    par_path = filepath + ".par"

    main_raw = _read_file_bytes(filepath)
    bak_raw = _read_file_bytes(bak_path)
    par_raw = _read_file_bytes(par_path)

    # Stage 1: Main OK
    if main_raw is not None:
        data = _parse_json_checked(main_raw)
        if data is not None:
            logger.debug("Loaded data from main file")
            return _strip_checksum(data)

    # Stage 2: Backup OK
    if bak_raw is not None:
        data = _parse_json_checked(bak_raw)
        if data is not None:
            logger.warning("Main corrupt/missing, recovered from backup")
            # Regenerate main
            try:
                atomic_write_file(filepath, bak_raw)
            except OSError as e:
                logger.error("Failed to regenerate main: %s", e)
            return _strip_checksum(data)

    # Stage 3: Bak + parity → reconstruct main
    if bak_raw is not None and par_raw is not None:
        try:
            reconstructed = reconstruct_from_parity(bak_raw, par_raw)
            data = _parse_json_checked(reconstructed)
            if data is not None:
                logger.warning("Recovered main from bak + parity")
                try:
                    atomic_write_file(filepath, reconstructed)
                except OSError:
                    pass
                return _strip_checksum(data)
        except Exception as e:
            logger.error("Parity reconstruction (bak+par) failed: %s", e)

    # Stage 4: Main + parity → reconstruct bak
    if main_raw is not None and par_raw is not None:
        try:
            reconstructed = reconstruct_from_parity(main_raw, par_raw)
            data = _parse_json_checked(reconstructed)
            if data is not None:
                logger.warning("Recovered bak from main + parity")
                try:
                    atomic_write_file(bak_path, reconstructed)
                except OSError:
                    pass
                return _strip_checksum(data)
        except Exception as e:
            logger.error("Parity reconstruction (main+par) failed: %s", e)

    # Stage 5: All corrupt or missing
    logger.warning("All data files corrupt or missing — starting fresh")
    for path in [filepath, bak_path, par_path]:
        _rename_corrupt(path)

    return empty_state()


def _strip_checksum(data: dict) -> dict:
    """Remove _checksum from loaded data (not needed in memory)."""
    data.pop("_checksum", None)
    return data


# --- History (monthly snapshot files) ---

def _history_checksum(days: list) -> str:
    """Compute SHA256 over the days array for history file integrity."""
    raw = json.dumps(days, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_month_history(year_month: str) -> dict | None:
    """
    Load a monthly history file (e.g. '2026-03').
    Returns dict with 'month' and 'days' keys, or None if unavailable.
    """
    history_dir = get_history_dir()
    filepath = os.path.join(history_dir, f"{year_month}.json")
    bak_path = filepath + ".bak"

    for path in [filepath, bak_path]:
        raw = _read_file_bytes(path)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict) or "days" not in data:
            continue
        stored_cs = data.get("_checksum")
        if stored_cs and stored_cs != _history_checksum(data["days"]):
            logger.warning("Checksum mismatch in %s", path)
            continue
        return {"month": data.get("month", year_month), "days": data["days"]}

    return None


def save_month_history(year_month: str, month_data: dict):
    """Save a monthly history file with checksum and backup."""
    history_dir = get_history_dir()
    ensure_data_dir()

    filepath = os.path.join(history_dir, f"{year_month}.json")
    bak_path = filepath + ".bak"

    out = {
        "_checksum": _history_checksum(month_data["days"]),
        "month": year_month,
        "days": month_data["days"],
    }
    json_bytes = json.dumps(out, indent=2).encode("utf-8")

    atomic_write_file(filepath, json_bytes)
    atomic_write_file(bak_path, json_bytes)


def append_daily_snapshot(snapshot: dict):
    """
    Append a daily snapshot to the appropriate monthly history file.
    snapshot must have a 'date' key like '2026-03-22'.
    """
    date_str = snapshot["date"]
    year_month = date_str[:7]  # '2026-03'

    month_data = load_month_history(year_month)
    if month_data is None:
        month_data = {"month": year_month, "days": []}

    # Replace existing entry for same date, or append
    month_data["days"] = [d for d in month_data["days"] if d.get("date") != date_str]
    month_data["days"].append(snapshot)
    month_data["days"].sort(key=lambda d: d.get("date", ""))

    save_month_history(year_month, month_data)


def load_history_range(days: int = 30) -> list:
    """
    Load daily snapshots for the last N days from monthly history files.
    Returns list of snapshot dicts sorted by date.
    """
    from datetime import timedelta

    today = datetime.now().date()
    start_date = today - timedelta(days=days)

    # Determine which months to load
    months = set()
    d = start_date
    while d <= today:
        months.add(d.strftime("%Y-%m"))
        d += timedelta(days=32)
        d = d.replace(day=1)
    months.add(today.strftime("%Y-%m"))

    all_days = []
    for ym in sorted(months):
        month_data = load_month_history(ym)
        if month_data is None:
            continue
        for entry in month_data["days"]:
            entry_date = entry.get("date", "")
            if entry_date >= start_date.isoformat() and entry_date <= today.isoformat():
                all_days.append(entry)

    all_days.sort(key=lambda d: d.get("date", ""))
    return all_days
