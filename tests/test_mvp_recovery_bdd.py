"""Recovery acceptance uses disposable files and the distributed CLI."""
import hashlib
import json
import sqlite3
import tarfile
import threading

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios("features/mvp/recovery.feature")


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    path = tmp_path / "ledger.db"
    monkeypatch.setenv("INVEST_DB", str(path))
    return {"path": path, "tmp": tmp_path, "runner": CliRunner()}


def invoke(ctx, *args):
    return ctx["runner"].invoke(app, list(args))


def successful(result):
    assert result.exit_code == 0, f"Required recovery command failed: {result.output}"
    return json.loads(result.stdout)


@given("a disposable accepted recovery ledger")
def accepted(recovery):
    ledger = Ledger(recovery["path"])
    ledger.apply({"account": {"id": "fictional", "name": "Fictional IRA",
                              "tax_status": "TAX_FREE"},
                  "positions": [{"security": "DEMO", "quantity": "10",
                                 "price": "100", "market_value": "1000",
                                 "displayed_price_precision": 2,
                                 "displayed_market_value_precision": 2}],
                  "cash": "100", "cash_known": True,
                  "source_timestamp": "2026-10-09", "source_hash": "fictional",
                  "data_environment": "SYNTHETIC"})
    recovery["state"] = ledger.state()
    ledger.connection.close()
    recovery["archive"] = recovery["tmp"] / "archive.tar.gz"


@when("an online recovery archive is created")
def backup(recovery):
    reader = sqlite3.connect(recovery["path"])
    # B01 tests backup consistency; the separate first-install scenario tests
    # writer configuration. Prepare WAL so the old reader cannot block setup.
    reader.execute("PRAGMA journal_mode=WAL")
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM accounts").fetchone()
    started = threading.Event()
    stop = threading.Event()
    errors = []

    def write_deposits():
        writer = Ledger(recovery["path"])
        try:
            for number in range(20):
                writer.record_activity({"activity_id": f"concurrent-{number}",
                    "account_id": "fictional", "type": "CASH_DEPOSIT",
                    "amount": "1", "date": "2026-10-10"}, yes=True)
                started.set()
                if stop.is_set():
                    break
        except Exception as error:
            errors.append(error)
            started.set()
        finally:
            writer.connection.close()

    thread = threading.Thread(target=write_deposits)
    thread.start()
    try:
        assert started.wait(5), "Synthetic writer did not start within bounded timeout"
        recovery["backup"] = invoke(recovery, "db", "backup", "--output", str(recovery["archive"]))
    finally:
        stop.set()
        thread.join(5)
        reader.close()
    assert not thread.is_alive()
    assert not errors, errors


@then("the archive verifies and restores the complete accepted state")
def roundtrip(recovery):
    successful(recovery["backup"])
    assert recovery["archive"].stat().st_mode & 0o777 == 0o600
    assert successful(invoke(recovery, "db", "verify", str(recovery["archive"])))["status"] == "AVAILABLE"
    successful(invoke(recovery, "db", "restore", str(recovery["archive"]), "--confirm"))
    ledger = Ledger(recovery["path"])
    state = ledger.state()
    deposits = [event for event in state["activities"] if event["type"] == "CASH_DEPOSIT"]
    assert 1 <= len(deposits) <= 20
    assert state["cash_balances"][0]["amount"] == str(100 + len(deposits))
    assert state["positions"] == recovery["state"]["positions"]
    ledger.connection.close()


@given("a development schema nine ledger")
def old(recovery):
    connection = sqlite3.connect(recovery["path"])
    connection.execute("CREATE TABLE original (value TEXT)")
    connection.execute("INSERT INTO original VALUES ('preserve')")
    connection.execute("PRAGMA user_version=9")
    connection.commit()
    connection.close()
    recovery["bytes"] = recovery["path"].read_bytes()


@when("new-design database status is requested")
def status(recovery):
    recovery["result"] = invoke(recovery, "db", "status")


@then("the unsupported schema is reported without changing any bytes")
def unchanged(recovery):
    result = recovery["result"]
    assert result.exit_code == 3, result.output
    assert "UNSUPPORTED_DEVELOPMENT_SCHEMA" in result.stderr
    assert recovery["path"].read_bytes() == recovery["bytes"]


@given("a damaged SQLite ledger")
def corrupt(recovery):
    recovery["path"].write_bytes(b"not a sqlite database")


@when("database verification is requested")
def verify_db(recovery):
    recovery["result"] = invoke(recovery, "db", "verify", str(recovery["path"]))


@then("verification reports a specific non-success integrity result")
def integrity(recovery):
    result = successful(recovery["result"])
    assert result["status"] in {"BLOCKED", "UNAVAILABLE"}
    assert any(issue["code"] == "SQLITE_INTEGRITY_FAILED" for issue in result["issues"])


@given("a recovery archive with a tampered referenced artifact")
def tampered(recovery):
    artifact = recovery["tmp"] / "history.parquet"
    artifact.write_bytes(b"tampered synthetic artifact")
    manifest = recovery["tmp"] / "manifest.json"
    manifest.write_text(json.dumps({"files": [{"path": "history.parquet",
        "size": artifact.stat().st_size, "sha256": hashlib.sha256(b"original").hexdigest()}]}))
    recovery["archive"] = recovery["tmp"] / "tampered.tar.gz"
    with tarfile.open(recovery["archive"], "w:gz") as archive:
        archive.add(artifact, arcname="history.parquet")
        archive.add(manifest, arcname="manifest.json")


@when("recovery verification is requested")
def verify_archive(recovery):
    recovery["result"] = invoke(recovery, "db", "verify", str(recovery["archive"]))


@then("the artifact is identified and replacement is refused")
def invalid_artifact(recovery):
    result = successful(recovery["result"])
    assert result["status"] == "BLOCKED"
    assert any("history.parquet" in issue["affected_ids"] for issue in result["issues"])
    assert not recovery["path"].exists()


@when("recovery preview and confirmed replacement are requested separately")
def preview(recovery):
    successful(invoke(recovery, "db", "backup", "--output", str(recovery["archive"])))
    recovery["before"] = recovery["path"].read_bytes()
    recovery["preview"] = invoke(recovery, "db", "restore", str(recovery["archive"]), "--dry-run")
    recovery["after_preview"] = recovery["path"].read_bytes()
    recovery["restore"] = invoke(recovery, "db", "restore", str(recovery["archive"]), "--confirm")


@then("preview preserves the ledger and confirmation restores the archived state")
def restored(recovery):
    successful(recovery["preview"])
    assert recovery["before"] == recovery["after_preview"]
    successful(recovery["restore"])
    ledger = Ledger(recovery["path"])
    assert ledger.state() == recovery["state"]
    ledger.connection.close()


@given("a recovery archive containing a traversal member")
def traversal(recovery):
    import io
    recovery["archive"] = recovery["tmp"] / "unsafe.tar.gz"
    with tarfile.open(recovery["archive"], "w:gz") as archive:
        member = tarfile.TarInfo("../escaped")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"evil"))


@then("unsafe members block verification without writing outside staging")
def refused_member(recovery):
    result = successful(recovery["result"])
    assert result["status"] == "BLOCKED"
    assert any(issue["code"] == "UNSAFE_ARCHIVE_MEMBER" for issue in result["issues"])
    assert not (recovery["tmp"].parent / "escaped").exists()


@given("an empty new-design ledger path")
def empty_new(recovery):
    assert not recovery["path"].exists()


@then("schema one has relational balances and durable writer settings")
def durable(recovery):
    result = successful(recovery["result"])
    assert result["schema_version"] == 1
    assert result["writer_settings"] == {"foreign_keys": True, "journal_mode": "wal",
                                         "synchronous": "FULL", "busy_timeout": 5000}
    connection = sqlite3.connect(recovery["path"])
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(position_balances)")}
        assert {"account_id", "security_id", "quantity", "currency"} <= columns
        assert "data" not in columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()
