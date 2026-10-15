"""Synthetic-only immutable dataset and deployment acceptance."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError

scenarios("features/mvp/datasets.feature")


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("INVEST_DB", str(tmp_path / "ledger.db"))
    monkeypatch.delenv("INVEST_BIND", raising=False)
    ledger = Ledger(tmp_path / "ledger.db")
    yield {"tmp": tmp_path, "ledger": ledger}
    ledger.connection.close()


@given("a fictional history response containing only unadjusted close")
def unadjusted(dataset):
    path = dataset["tmp"] / "provider.json"
    path.write_text(json.dumps({"history": {"DEMO": [
        {"date": "2026-10-08", "close": "100"},
        {"date": "2026-10-09", "close": "110"}]}}))
    dataset["client"] = MarketClient(dataset["ledger"], fixture_path=path)


@when("total return history is requested")
def history(dataset):
    dataset["result"] = dataset["client"].history("DEMO")


@then("adjusted return is unavailable with a typed missing-field issue")
def unavailable(dataset):
    result = dataset["result"]
    assert result["status"] == "UNAVAILABLE"
    assert any(issue["code"] == "MISSING_DIVIDEND_ADJUSTED_PRICE" for issue in result["issues"])
    assert result["data_environment"] == "SYNTHETIC"


def analytics():
    try:
        return importlib.import_module("invest.analytics_store")
    except ModuleNotFoundError:
        pytest.fail("Pinned immutable analytical dataset reader is required")


@given("two synthetic fund holdings vintages")
def vintages(dataset):
    dataset["vintages"] = [
        {"id": "sep", "kind": "fund_holdings", "security_id": "FUND",
         "observed_at": "2026-09-01", "as_of": "2026-08-31",
         "data_environment": "SYNTHETIC", "rows": [{"security_id": "OLD", "weight": "1"}]},
        {"id": "oct", "kind": "fund_holdings", "security_id": "FUND",
         "observed_at": "2026-10-01", "as_of": "2026-09-30",
         "data_environment": "SYNTHETIC", "rows": [{"security_id": "NEW", "weight": "1"}]}]


@when("the September holdings snapshot is requested")
def selected(dataset):
    dataset["result"] = analytics().select_vintage(dataset["vintages"],
        security_id="FUND", as_of="2026-09-15")


@then("only the September eligible vintage is returned")
def eligible(dataset):
    assert dataset["result"]["id"] == "sep"
    assert dataset["result"]["rows"] == [{"security_id": "OLD", "weight": "1"}]


@given("a frozen synthetic analytical dataset")
def frozen(dataset):
    artifact = Path("tests/fixtures/mvp-history.parquet")
    dataset["manifest"] = {"id": "frozen", "data_environment": "SYNTHETIC",
        "artifacts": [{"path": str(artifact), "sha256": hashlib.sha256(
            artifact.read_bytes()).hexdigest(), "kind": "adjusted_history"}]}
    dataset["before"] = dataset["ledger"].state()


@when("the pinned analytical dataset is read twice")
def twice(dataset):
    reader = analytics()
    dataset["first"] = reader.read_snapshot(dataset["ledger"], dataset["manifest"])
    dataset["second"] = reader.read_snapshot(dataset["ledger"], dataset["manifest"])


@then("the results and fingerprints agree without changing the ledger")
def reproducible(dataset):
    assert dataset["first"] == dataset["second"]
    assert dataset["first"]["manifest_ids"] == ["frozen"]
    assert dataset["first"]["source_fingerprint"]
    assert dataset["first"]["rows"] == [
        {"security_id": "DEMO", "date": "2026-10-09", "adjusted_close": "100"}]
    assert dataset["ledger"].state() == dataset["before"]


@given("a disposable inspection path")
def inspection(dataset):
    pass


@when("native inspection attempts to bind externally")
def external(dataset):
    from invest.web import create_server
    try:
        server = create_server(dataset["tmp"] / "web.db", host="0.0.0.0", port=0)
    except DomainError as error:
        dataset["error"] = error
    else:
        server.server_close()
        dataset["error"] = None


@then("the bind is refused and Compose publishes only loopback")
def loopback(dataset):
    assert dataset["error"] is not None
    # Native refusal is exercised above; retain the Docker publication safety rule
    # because the offline app image has no resolved Compose configuration surface.
    assert '127.0.0.1:8765:8765' in Path("compose.yaml").read_text()


@given("an offline fresh checkout")
def checkout(dataset):
    pass


@when("installed workflow discovery is requested")
def discovery(dataset):
    dataset["result"] = CliRunner().invoke(app, ["research", "skills", "list"])


@then("seven portfolio workflows and safe backup instructions are discoverable")
def workflows(dataset):
    result = dataset["result"]
    assert result.exit_code == 0, result.output
    output = result.stdout
    for name in ("portfolio-sync", "portfolio-performance", "monthly-investing",
                 "tax-loss-harvesting", "investment-screening", "portfolio-research",
                 "portfolio-strategy"):
        assert f"investobot-{name}" in output
    backup = CliRunner().invoke(app, ['tools', 'describe', 'db.backup'])
    assert backup.exit_code == 0, backup.output
    descriptor = json.loads(backup.stdout)
    assert descriptor['name'] == 'db.backup'
    assert any('--output' in option['flags'] for option in descriptor['options'])


@when("analytical runtime capabilities are requested")
def capabilities(dataset):
    dataset["result"] = analytics().capabilities()


@then("DuckDB and sqlite vec report pinned offline availability")
def offline_extensions(dataset):
    result = dataset["result"]
    assert result["duckdb"]["available"] is True
    assert result["duckdb"]["implicit_download"] is False
    assert result["sqlite_vec"]["available"] is True
    for key in ("duckdb_sqlite_extension", "sqlite_vec"):
        assert len(result[key]["sha256"]) == 64
        assert result[key]["version"]


@when("a referenced artifact changes after its manifest is frozen")
def corrupt_artifact(dataset):
    artifact = dataset["tmp"] / "damaged.parquet"
    artifact.write_bytes(Path(dataset["manifest"]["artifacts"][0]["path"]).read_bytes() + b"corruption")
    dataset["manifest"]["artifacts"][0]["path"] = str(artifact)
    dataset["result"] = analytics().read_snapshot(dataset["ledger"], dataset["manifest"])


@then("the pinned analytical read is blocked by the exact artifact hash mismatch")
def hash_mismatch(dataset):
    result = dataset["result"]
    assert result["status"] == "BLOCKED"
    assert result["rows"] is None
    assert any(issue["code"] == "ARTIFACT_HASH_MISMATCH" and
               str(dataset["tmp"] / "damaged.parquet") in issue["affected_ids"]
               for issue in result["issues"])
    assert dataset["ledger"].state() == dataset["before"]


@given("a fictional undated quote response")
def quote_fixture(dataset):
    path = dataset["tmp"] / "quote.json"
    path.write_text(json.dumps({"quote": {"DEMO": [{"price": "100"}]}}))
    dataset["client"] = MarketClient(dataset["ledger"], fixture_path=path)


@when("its quote is retrieved")
def quote(dataset):
    dataset["result"] = dataset["client"].quote("DEMO")


@then("retrieval time does not make the source quote current")
def unknown_quote(dataset):
    result = dataset["result"]
    assert result["data_as_of"] is None
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(issue["code"] == "UNKNOWN_SOURCE_DATE" for issue in result["issues"])
    assert result["data_environment"] == "SYNTHETIC"
