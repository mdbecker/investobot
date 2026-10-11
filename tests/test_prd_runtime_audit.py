"""Runtime promises from the active PRD, independent of release test counts."""

import tomllib
from pathlib import Path

import pytest

from invest.bonds import analyze


def test_default_runtime_uses_existing_numerical_dependencies_for_plain_bonds():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert not any(value.lower().startswith("quantlib")
                   for value in project["project"]["dependencies"])


@pytest.mark.parametrize("instrument_type", ["CALLABLE", "CONVERTIBLE", "STRUCTURED"])
def test_unsupported_bond_structure_has_no_invented_plain_bond_metrics(instrument_type):
    result = analyze({
        "instrument_type": instrument_type,
        "face_value": "1000", "coupon": "0.05", "clean_price": "100",
        "issue_date": "2021-01-15", "settlement_date": "2026-01-15",
        "maturity": "2031-01-15", "frequency": 2,
        "day_count": "ACTUAL_ACTUAL_BOND",
    })
    assert result["status"] == "UNAVAILABLE"
    assert result["issues"]
    assert "yield_to_maturity" not in result


def test_regular_par_bond_has_disclosed_cash_flow_solution():
    result = analyze({
        "face_value": "1000", "coupon": "0.05", "clean_price": "100",
        "issue_date": "2021-01-15", "settlement_date": "2026-01-15",
        "maturity": "2031-01-15", "frequency": 2,
        "day_count": "ACTUAL_ACTUAL_BOND",
    })
    assert result["status"] == "CALCULATED"
    assert abs(float(result["yield_to_maturity"]) - .05) < 1e-9
    assert float(result["accrued_interest"]) == 0
    assert float(result["dirty_value"]) == 1000
