"""Deterministic public performance gates; timings here are synthetic, not measurements."""
from copy import deepcopy
from importlib import import_module

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/performance/gates.feature")


def sample(elapsed=1_000_000_000):
    return {"elapsed_ns": elapsed, "peak_rss_bytes": 1000, "persisted_bytes": 1000,
            "temp_bytes": 1000, "exit_code": 0, "output_hash": "a" * 64,
            "counts": {"positions": 1000}}


def context():
    fixture = {"recipe_version": "1", "hash": "b" * 64,
               "dimensions": {"positions": 1000}, "seed": 271828}
    runner = {"id": "same-runner", "platform": "linux/amd64", "cpus": 2,
              "memory_bytes": 4294967296, "network": "none",
              "threads": 1, "documented_laptop_equivalent": True}
    manifest = {"mode": "pr", "fixture": fixture, "runner": runner,
                "required_cases": ["P07.monthly"], "reference_commit": "reference",
                "reference_hash": "c" * 64, "expected_reference_hash": "c" * 64,
                "reproduction_command": "python scripts/perf.py run --case P07.monthly"}
    reports = [{"commit": commit, "fixture": deepcopy(fixture),
                "runner": deepcopy(runner), "cases": {"P07.monthly": {
                    "status": "OK", "samples": [sample() for _ in range(7)]}}}
               for commit in ("candidate", "base", "reference")]
    return reports, manifest


@pytest.fixture
def gate_case():
    return {}


@given("fixed synthetic benchmark-result JSON")
def fixed(gate_case):
    gate_case["reports"], gate_case["manifest"] = context()


@when(parsers.parse('the public gate evaluates "{rule}"'))
def evaluate(gate_case, rule):
    # Deferred import makes each absent public capability an observed scenario red.
    gates = import_module("benchmarks.gates")
    candidate, base, reference = gate_case["reports"]
    manifest = gate_case["manifest"]
    result_case = candidate["cases"]["P07.monthly"]
    gate_case["rule"] = rule
    if rule.startswith("aggregate_"):
        modes = {"aggregate_pr": ("pr", 7), "aggregate_retrieval": ("extended_retrieval", 21),
                 "aggregate_bulk": ("extended_bulk", 3)}
        mode, count = modes.get(rule, ("pr", 6))
        rows = [sample(i * 200_000_000) for i in range(1, count + 1)]
        gate_case["result"] = gates.aggregate(rows, mode)
        return
    if rule.startswith("scaling_"):
        small = deepcopy(base)
        large = deepcopy(base)
        large["fixture"]["dimensions"]["positions"] = 4000
        for row in large["cases"]["P07.monthly"]["samples"]:
            row["counts"]["positions"] = 4000
            row["elapsed_ns"] *= 8 if rule == "scaling_fail" else 6
        if rule == "scaling_wrong_counts":
            large["cases"]["P07.monthly"]["samples"][0]["counts"]["positions"] = 3999
        gate_case["result"] = gates.compare_scaling([{
            "case_id": "P07.monthly", "small": small, "large": large,
            "expected_complexity": "linear"}])
        return
    if rule.startswith("inventory_"):
        cases = [{"id": "P07.monthly", "workflow": "plan propose", "runnable": True,
                  "required": True, "modes": ["pr", "extended"],
                  "family": "P07", "operation": "plan propose", "profile": "medium",
                  "boundary": "public operation", "mutates": True, "repetitions": 7,
                  "metrics": ["elapsed_ns", "peak_rss_bytes", "persisted_bytes", "temp_bytes"],
                  "invariant": "expected positions and proposal count",
                  "scalability_partner": "P07.monthly.stress", "budget_ns": 10_000_000_000,
                  "budget_stat": "p95"}]
        descriptors = [{"command": "plan propose", "performance": "expensive",
                        "required_cases": ["P07.monthly"]}]
        if rule == "inventory_missing":
            cases = []
        elif rule == "inventory_unrunnable":
            cases[0]["runnable"] = False
        elif rule == "inventory_unclassified":
            descriptors.append({"command": "new expensive query", "performance": "expensive"})
        elif rule == "inventory_missing_extended":
            cases[0]["modes"] = ["pr"]
        inventory = {"required_cases": ["P07.monthly"], "cases": cases}
        gate_case["result"] = gates.validate_inventory(inventory, descriptors)
        return
    if rule.startswith("budget_"):
        manifest["mode"] = "extended_retrieval"
        result_case["samples"] = [sample(2_000_000_001 if rule == "budget_fail" else 2_000_000_000)
                                  for _ in range(21)]
        if rule == "budget_wrong_runner":
            candidate["runner"]["cpus"] = 8
        gate_case["result"] = gates.certify(candidate, [{
            "id": "P07.monthly", "budget_ns": 2_000_000_000, "budget_stat": "p95",
            "mode": "extended_retrieval"}])
        return
    if rule in {"median_fail", "diagnostics", "retry_pass", "retry_fail", "retry_error"}:
        for row in result_case["samples"]:
            row["elapsed_ns"] = 1_260_000_000
    elif rule == "median_tie":
        for row in result_case["samples"]:
            row["elapsed_ns"] = 1_250_000_000
    elif rule == "median_unrounded":
        for row in result_case["samples"]:
            row["elapsed_ns"] = 1_250_000_001
    elif rule == "cumulative_fail":
        for row in reference["cases"]["P07.monthly"]["samples"]:
            row["elapsed_ns"] = 790_000_000
    elif rule.startswith("resource_"):
        metric = rule.removeprefix("resource_")
        for row in result_case["samples"]:
            row[metric] = 1300
            row["elapsed_ns"] = 500_000_000
    elif rule in {"p95_fail", "p95_tie"}:
        manifest["mode"] = "extended_retrieval"
        for report in (candidate, base, reference):
            report["cases"]["P07.monthly"]["samples"] = [sample() for _ in range(21)]
        candidate["cases"]["P07.monthly"]["samples"][-2:] = [
            sample(1_360_000_000 if rule == "p95_fail" else 1_350_000_000) for _ in range(2)]
    elif rule == "missing_case":
        candidate["cases"] = {}
    elif rule in {"timeout", "oom", "invalid_output"}:
        result_case["status"] = rule.upper()
    elif rule == "exit_error":
        result_case["samples"][0]["exit_code"] = 3
    elif rule == "wrong_output":
        result_case["samples"][0]["output_hash"] = "d" * 64
    elif rule == "omitted_records":
        for row in result_case["samples"]:
            row["counts"]["positions"] = 999
            row["elapsed_ns"] = 100_000_000
    elif rule == "fixture_changed":
        candidate["fixture"]["hash"] = "d" * 64
    elif rule == "dimensions_changed":
        candidate["fixture"]["dimensions"]["positions"] = 999
    elif rule == "recipe_changed":
        candidate["fixture"]["recipe_version"] = "2"
    elif rule == "runner_changed":
        candidate["runner"]["id"] = "different-machine"
    elif rule == "reference_changed":
        manifest["reference_commit"] = "candidate"
    elif rule == "baseline_rewritten":
        manifest["reference_hash"] = "d" * 64
    elif rule == "unapproved_rebaseline":
        manifest["reference_hash"] = "d" * 64
        manifest["rebaseline"] = {"approved": False, "reason": "slower", "reviewer": ""}
    elif rule == "self_asserted_rebaseline":
        manifest["reference_hash"] = "d" * 64
        manifest["rebaseline"] = {"approved": True, "reason": "slower", "reviewer": "self"}
    elif rule == "null_resource":
        result_case["samples"][0]["peak_rss_bytes"] = None
    elif rule == "negative_timing":
        result_case["samples"][0]["elapsed_ns"] = -1
    elif rule == "batch_repetitions_mismatch":
        for row in result_case["samples"]:
            row["batch_repetitions"] = 2
    elif rule == "short_batch":
        for report in (candidate, base, reference):
            for row in report["cases"]["P07.monthly"]["samples"]:
                row["elapsed_ns"] = 100_000_000
    elif rule == "insufficient_samples":
        result_case["samples"] = result_case["samples"][:6]
    if rule.startswith("retry_"):
        for report in (candidate, base, reference):
            retry = deepcopy(report["cases"]["P07.monthly"])
            if rule == "retry_pass":
                retry["samples"] = [sample() for _ in range(7)]
            if rule == "retry_error" and report is candidate:
                retry["status"] = "TIMEOUT"
            report["cases"]["P07.monthly"]["retry"] = retry
    gate_case["result"] = gates.compare(candidate, base, reference, manifest)


@then(parsers.parse('the outcome is "{expected}"'))
def outcome(gate_case, expected):
    result = gate_case["result"]
    rule = gate_case["rule"]
    if rule.startswith("aggregate_"):
        count = {"aggregate_pr": 7, "aggregate_retrieval": 21, "aggregate_bulk": 3}[rule]
        assert result["observations"] == count
        assert result["median_ns"] == ((count + 1) // 2) * 200_000_000
        assert result["max_ns"] == count * 200_000_000
        assert result["p95_ns"] == (4_000_000_000 if count == 21 else None)
        return
    assert result["status"] == expected
    if expected == "FAIL":
        assert result["issues"], "Failure must identify an actionable reason"
    if rule in {"median_fail", "diagnostics"}:
        assert result["retry_required"] == ["P07.monthly"]
        breach = next(row for row in result["issues"] if row.get("metric") == "elapsed_ns")
        assert breach["case_id"] == "P07.monthly"
        assert float(breach["ratio"]) == 1.26
        assert breach["candidate_commit"] == "candidate"
        assert breach["comparator_commit"] in {"base", "reference"}
        assert breach["counts"] == {"positions": 1000}
        assert breach["reproduction_command"] == gate_case["manifest"]["reproduction_command"]
    if rule == "cumulative_fail":
        assert any(row.get("comparator") == "reference" for row in result["issues"])
    if rule == "retry_pass":
        assert result["retries"], "A passing retry cannot erase the failed first measurement"
        assert result["retry_required"] == []


@pytest.mark.parametrize("budget_ns,mode,stat,count", [
    (2_000_000_000, "extended_retrieval", "p95", 21),
    (5_000_000_000, "extended_retrieval", "p95", 21),
    (10_000_000_000, "extended_retrieval", "p95", 21),
    (30_000_000_000, "extended_bulk", "max", 3),
    (180_000_000_000, "extended_bulk", "max", 3),
    (120_000_000_000, "extended_bulk", "max", 3),
])
@pytest.mark.parametrize("excess,expected", [(0, "PASS"), (1, "FAIL")])
def test_absolute_budget_inclusive_boundary(budget_ns, mode, stat, count, excess, expected):
    gates = import_module("benchmarks.gates")
    reports, _ = context()
    report = reports[0]
    report["cases"]["P07.monthly"]["samples"] = [sample(budget_ns + excess)
                                                  for _ in range(count)]
    outcome = gates.certify(report, [{"id": "P07.monthly", "budget_ns": budget_ns,
                                     "budget_stat": stat, "mode": mode}])
    assert outcome["status"] == expected
    if excess:
        assert outcome["issues"]


def test_aggregate_normalizes_common_batch_without_changing_source_counts():
    gates = import_module("benchmarks.gates")
    rows = [sample(2_000_000_000) for _ in range(7)]
    for row in rows:
        row["batch_repetitions"] = 10
    original = deepcopy(rows)
    result = gates.aggregate(rows, "pr")
    assert result["median_ns"] == 200_000_000
    assert result["max_ns"] == 200_000_000
    assert result["observations"] == 7
    assert result["p95_ns"] is None
    assert rows == original
