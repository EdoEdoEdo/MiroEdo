"""Tests for RunStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runs import RunStore


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(base_dir=tmp_path)


def _create(store: RunStore, **overrides):
    defaults = dict(
        mode="quick",
        brand="Mulino Bianco",
        source_type="brandwatch_csv",
        source_filename="demo.csv",
        enable_simulation=False,
    )
    defaults.update(overrides)
    return store.create(**defaults)


def test_create_persists_pending_run(store: RunStore) -> None:
    rec = _create(store)
    assert rec.status == "pending"
    assert rec.run_id and len(rec.run_id) == 32
    assert (store.base_dir / f"{rec.run_id}.json").exists()


def test_get_returns_same_record(store: RunStore) -> None:
    rec = _create(store)
    fetched = store.get(rec.run_id)
    assert fetched.run_id == rec.run_id
    assert fetched.brand == "Mulino Bianco"


def test_get_missing_raises(store: RunStore) -> None:
    with pytest.raises(KeyError):
        store.get("doesnotexist")


def test_mark_succeeded_updates_status_and_result(store: RunStore) -> None:
    rec = _create(store)
    updated = store.mark_succeeded(rec.run_id, result={"report_md": "# hi"})
    assert updated.status == "succeeded"
    assert updated.result == {"report_md": "# hi"}
    assert updated.updated_at >= rec.updated_at


def test_mark_failed_records_error(store: RunStore) -> None:
    rec = _create(store)
    updated = store.mark_failed(rec.run_id, error="boom")
    assert updated.status == "failed"
    assert updated.error == "boom"


def test_set_progress_merges_keys(store: RunStore) -> None:
    rec = _create(store)
    store.set_progress(rec.run_id, step="parse", pct=10)
    store.set_progress(rec.run_id, pct=50)
    fetched = store.get(rec.run_id)
    assert fetched.progress == {"step": "parse", "pct": 50}


def test_list_returns_newest_first(store: RunStore) -> None:
    import time

    a = _create(store, brand="A")
    time.sleep(0.01)
    b = _create(store, brand="B")
    time.sleep(0.01)
    c = _create(store, brand="C")
    ids = [r.run_id for r in store.list()]
    assert ids[0] == c.run_id
    assert set(ids) == {a.run_id, b.run_id, c.run_id}


def test_list_skips_corrupted_files(store: RunStore, tmp_path: Path) -> None:
    rec = _create(store)
    (store.base_dir / "garbage.json").write_text("not json", encoding="utf-8")
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].run_id == rec.run_id


def test_invalid_run_id_rejected(store: RunStore) -> None:
    with pytest.raises(ValueError):
        store.get("../etc/passwd")
    with pytest.raises(ValueError):
        store.get("a/b")


def test_atomic_write_no_tmp_left(store: RunStore) -> None:
    rec = _create(store)
    store.mark_succeeded(rec.run_id, result={"x": 1})
    leftovers = list(store.base_dir.glob("*.tmp"))
    assert leftovers == []


def test_round_trip_via_disk(store: RunStore) -> None:
    rec = _create(store, mode="full", enable_simulation=True)
    raw = json.loads((store.base_dir / f"{rec.run_id}.json").read_text())
    assert raw["mode"] == "full"
    assert raw["enable_simulation"] is True
    assert raw["status"] == "pending"
