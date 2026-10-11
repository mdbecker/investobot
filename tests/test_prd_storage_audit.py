"""Saved calculations identify their actual storage contract."""

from invest.ledger import Ledger
from invest.plan_storage import load_plan, save_plan, summaries


def test_saved_plan_and_compact_projection_pin_storage_schema_identity(tmp_path):
    selected = Ledger(tmp_path / "fictional.db")
    try:
        checksum = selected.connection.execute(
            "SELECT checksum FROM schema_migrations WHERE id='001'"
        ).fetchone()[0]
        save_plan(selected, {
            "id": "fictional-calculation", "source_state": selected.planning_state(),
            "created_at": "2026-10-11T12:00:00Z", "as_of": "2026-10-11",
            "status": "BLOCKED", "data_environment": "SYNTHETIC",
            "issues": [{"code": "NO_ACCEPTED_ACCOUNTS"}], "proposed_actions": [],
        })
        result = load_plan(selected, "fictional-calculation")
        assert result["storage_identity"] == {"schema_version": 1, "manifest_hash": checksum}
        compact = summaries(selected)[0]["summary"]
        assert compact["storage_identity"] == result["storage_identity"]
    finally:
        selected.connection.close()
