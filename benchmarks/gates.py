"""Pure deterministic gates over measured reports; never runs or rewrites baselines."""

from fractions import Fraction
from math import ceil
from statistics import median

MODES = {"pr": 7, "extended_retrieval": 21, "extended_bulk": 3}
METRICS = ("elapsed_ns", "peak_rss_bytes", "persisted_bytes", "temp_bytes")


def _runtime_identity(runner):
    # Keep these in archived reports, but they do not describe runner equivalence.
    return {key: value for key, value in runner.items()
            if key not in {"source_hash", "measurement_wall_seconds"}}


def _case_mode(manifest, identity):
    if manifest.get("mode") in MODES:
        return manifest["mode"]
    definition = next((row for row in manifest.get("cases", []) if row.get("id") == identity), {})
    suite = manifest.get("suite", "pr")
    if suite == "pr":
        return "pr"
    repetitions = definition.get("repetitions", {})
    count = repetitions.get("extended") if isinstance(repetitions, dict) else repetitions
    return "extended_bulk" if count == 3 else "extended_retrieval"


def _number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("A finite nonnegative numeric measurement is required")
    result = Fraction(str(value))
    if result < 0:
        raise ValueError("Negative measurement")
    return result


def _batch(row):
    value = row.get("batch_repetitions", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Positive integral batch_repetitions required")
    return value


def _public(value):
    return int(value) if value.denominator == 1 else float(value)


def _times(samples):
    return sorted(_number(row["elapsed_ns"]) / _batch(row) for row in samples)


def aggregate(samples, mode):
    """Median/max per logical operation; nearest-rank p95 only for 21 observations."""
    if mode not in MODES or len(samples) != MODES[mode]:
        raise ValueError("Wrong observation count or measurement mode")
    times = _times(samples)
    return {"median_ns": _public(median(times)), "max_ns": _public(max(times)),
            "p95_ns": _public(times[ceil(len(times) * .95) - 1]) if mode == "extended_retrieval" else None,
            "observations": len(samples)}


def _outcome(issues, **extra):
    return {"status": "FAIL" if issues else "PASS", "issues": issues, **extra}


def validate_inventory(manifest, descriptors):
    """Check executable inventory and classify every public expensive command."""
    issues = []
    rows = manifest.get("cases", [])
    ids = [row.get("id") for row in rows]
    for identity in manifest.get("required_cases", []):
        matches = [row for row in rows if row.get("id") == identity]
        if len(matches) != 1 or not matches[0].get("runnable", True):
            issues.append({"code": "MISSING_RUNNABLE_CASE", "case_id": identity})
        elif not {"pr", "extended"}.issubset(set(matches[0].get("modes", ["pr", "extended"]))):
            issues.append({"code": "MISSING_SUITE_COVERAGE", "case_id": identity})
    if len(ids) != len(set(ids)):
        issues.append({"code": "DUPLICATE_CASE"})
    for descriptor in descriptors:
        command = descriptor.get("command", descriptor.get("name"))
        if descriptor.get("performance") == "expensive":
            required = descriptor.get("required_cases", [])
            if not required or any(identity not in ids for identity in required):
                issues.append({"code": "UNCLASSIFIED_EXPENSIVE_WORKFLOW", "command": command})
        elif descriptor.get("performance") == "exempt" and not descriptor.get("reason"):
            issues.append({"code": "MISSING_EXEMPTION_REASON", "command": command})
    return _outcome(issues)


def _validate_case(case, mode, expected=None):
    issues = []
    if not case or case.get("status") not in {"OK", "PASS"}:
        return [{"code": "INVALID_CASE_RESULT", "observed": case.get("status") if case else "MISSING"}]
    samples = case.get("samples", [])
    if mode not in MODES or len(samples) != MODES[mode]:
        issues.append({"code": "INVALID_OBSERVATION_COUNT"})
    for row in samples:
        try:
            batch = _batch(row)
            for metric in METRICS:
                _number(row[metric])
            if _number(row["elapsed_ns"]) < 200_000_000:
                issues.append({"code": "INSUFFICIENT_BATCH_WORK"})
            if row.get("exit_code") != 0:
                issues.append({"code": "OPERATION_FAILED"})
            if not row.get("output_hash") or not isinstance(row.get("counts"), dict):
                issues.append({"code": "MISSING_OUTPUT_EVIDENCE"})
            for invariant in row.get("invariant_results", {}).values():
                if invariant.get("passed") is not True:
                    issues.append({"code": "INCORRECT_OUTPUT"})
            if expected and (row.get("output_hash") != expected.get("output_hash")
                             or row.get("counts") != expected.get("counts")):
                issues.append({"code": "INCORRECT_OUTPUT"})
            if expected and batch != _batch(expected):
                issues.append({"code": "BATCH_REPETITIONS_MISMATCH"})
        except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError):
            issues.append({"code": "INVALID_MEASUREMENT"})
    return issues


def _metric(case, metric, mode):
    rows = case["samples"]
    if metric == "elapsed_ns":
        times = _times(rows)
        return median(times)
    return max(_number(row[metric]) for row in rows)


def _ratio(candidate, comparator):
    if comparator == 0:
        return Fraction(1) if candidate == 0 else None
    return candidate / comparator


def _paired(candidate, base, reference, manifest, retry=False):
    issues, comparisons, retry_required = [], [], []
    for identity in manifest["required_cases"]:
        mode = _case_mode(manifest, identity)
        cases = [report.get("cases", {}).get(identity) for report in (candidate, base, reference)]
        if retry:
            cases = [case.get("retry") if case else None for case in cases]
        reference_samples = (cases[2] or {}).get("samples", [])
        expected = reference_samples[0] if reference_samples else {}
        invalid = []
        for report, case in zip((candidate, base, reference), cases):
            invalid.extend({**issue, "case_id": identity, "commit": report.get("commit")}
                           for issue in _validate_case(case, mode, expected))
        if invalid:
            issues.extend(invalid)
            continue
        for label, report, comparator in zip(("base", "reference"), (base, reference), cases[1:]):
            for metric in METRICS + (("p95_ns",) if mode == "extended_retrieval" else ()):
                if metric == "p95_ns":
                    left = _times(cases[0]["samples"])[19]
                    right = _times(comparator["samples"])[19]
                    limit = Fraction(135, 100)
                else:
                    left, right = _metric(cases[0], metric, mode), _metric(comparator, metric, mode)
                    limit = Fraction(125, 100)
                ratio = _ratio(left, right)
                row = {"case_id": identity, "metric": metric, "comparator": label,
                       "ratio": _public(ratio) if ratio is not None else None,
                       "candidate_commit": candidate.get("commit"), "comparator_commit": report.get("commit"),
                       "counts": expected["counts"], "reproduction_command": manifest.get("reproduction_command"),
                       "candidate_value": _public(left), "comparator_value": _public(right)}
                comparisons.append(row)
                if ratio is None or ratio > limit:
                    issues.append({"code": "PERFORMANCE_REGRESSION", **row})
                    if identity not in retry_required:
                        retry_required.append(identity)
    return issues, comparisons, retry_required


def compare(candidate, base, reference, manifest):
    """Both comparators must pass; one complete fresh retry cannot hide bad outputs."""
    issues = []
    if (manifest.get("reference_hash") != manifest.get("expected_reference_hash")
            or reference.get("commit") != manifest.get("reference_commit")):
        # Approval must be established by trusted CI outside the untrusted result JSON.
        issues.append({"code": "UNAPPROVED_REFERENCE_CHANGE"})
    for report in (candidate, base, reference):
        if report.get("fixture") != manifest.get("fixture"):
            issues.append({"code": "FIXTURE_PROVENANCE_MISMATCH", "commit": report.get("commit")})
        if _runtime_identity(report.get("runner", {})) != _runtime_identity(manifest.get("runner", {})):
            issues.append({"code": "RUNNER_MISMATCH", "commit": report.get("commit")})
    if issues:
        return _outcome(issues, comparisons=[], retry_required=[], retries=[])
    issues, comparisons, required = _paired(candidate, base, reference, manifest)
    retries = []
    remaining = []
    for identity in required:
        if all(report.get("cases", {}).get(identity, {}).get("retry") is not None
               for report in (candidate, base, reference)):
            retry_manifest = {**manifest, "required_cases": [identity]}
            retry_issues, retry_comparisons, _ = _paired(candidate, base, reference, retry_manifest, retry=True)
            retries.append({"case_id": identity, "status": "FAIL" if retry_issues else "PASS",
                            "issues": retry_issues, "comparisons": retry_comparisons})
            if not retry_issues:
                issues = [row for row in issues if not (row.get("case_id") == identity
                          and row.get("code") == "PERFORMANCE_REGRESSION")]
            else:
                issues.extend(retry_issues)
        else:
            remaining.append(identity)
    result = _outcome(issues, comparisons=comparisons, retry_required=remaining, retries=retries)
    if not issues and retries:
        result["status"] = "NOISY_FIRST_MEASUREMENT"
    return result


def certify(report, cases):
    """Release certification requires the constrained documented runner and budgets."""
    issues = []
    runner = report.get("runner", {})
    if (runner.get("cpus") != 2 or runner.get("memory_bytes") != 4294967296
            or not runner.get("documented_laptop_equivalent")):
        issues.append({"code": "UNCERTIFIED_RUNNER"})
    if (("docker" in runner and runner["docker"] is not True)
            or ("network" in runner and runner["network"] != "none")
            or ("machine" in runner and runner["machine"] not in {"aarch64", "arm64", "x86_64", "amd64"})
            or ("platform" in runner and runner["platform"] not in {"linux/arm64", "linux/amd64", "linux/x86_64"})):
        issues.append({"code": "UNCERTIFIED_RUNTIME"})
    for definition in cases:
        identity = definition["id"]
        case = report.get("cases", {}).get(identity)
        if ("dimensions" in definition and (case or {}).get(
                "fixture_dimensions", report.get("fixture", {}).get("dimensions"))
                != definition["dimensions"]):
            issues.append({"code": "ABSOLUTE_WORKLOAD_MISMATCH", "case_id": identity})
        mode = definition.get("mode") or _case_mode({"suite": "extended", "cases": [definition]}, identity)
        failures = _validate_case(case, mode)
        if failures:
            issues.extend({**row, "case_id": identity} for row in failures)
            continue
        values = _times(case["samples"])
        stat = definition["budget_stat"]
        observed = values[ceil(len(values) * .95) - 1] if stat == "p95" else (
            max(values) if stat == "max" else median(values))
        if stat == "p95" and len(values) < 21:
            issues.append({"code": "INSUFFICIENT_P95_OBSERVATIONS", "case_id": identity})
        if observed > _number(definition["budget_ns"]):
            issues.append({"code": "ABSOLUTE_BUDGET_EXCEEDED", "case_id": identity,
                           "observed_ns": _public(observed), "budget_ns": definition["budget_ns"]})
    return _outcome(issues)


def compare_scaling(reports):
    """Matched logical records on one revision; no unexplained complexity exemption."""
    issues = []
    for pair in reports:
        identity = pair["case_id"]
        small, large = pair["small"], pair["large"]
        cases = [report.get("cases", {}).get(identity) for report in (small, large)]
        if (small.get("commit") != large.get("commit")
                or _runtime_identity(small.get("runner", {})) != _runtime_identity(large.get("runner", {}))):
            issues.append({"code": "SCALING_PROVENANCE_MISMATCH", "case_id": identity})
            continue
        counts = [(case or {}).get("samples", [{}])[0].get("counts", {}) for case in cases]
        if not counts[0] or counts[1] != {key: value * 4 for key, value in counts[0].items()}:
            issues.append({"code": "SCALING_COUNTS_MISMATCH", "case_id": identity})
            continue
        invalid = False
        for case, expected in zip(cases, counts):
            if not case or case.get("status") not in {"OK", "PASS"} or not case.get("samples"):
                invalid = True
                break
            for row in case["samples"]:
                if row.get("counts") != expected or row.get("exit_code") != 0:
                    invalid = True
        if invalid:
            issues.append({"code": "INVALID_SCALING_OUTPUT", "case_id": identity})
            continue
        try:
            ratio = _ratio(median(_times(cases[1]["samples"])), median(_times(cases[0]["samples"])))
            limit = Fraction(6)
            if pair.get("expected_complexity") != "linear":
                if not pair.get("complexity_reason") or not pair.get("upper_ratio"):
                    raise ValueError("Missing measured nonlinear bound")
                limit = _number(pair["upper_ratio"])
            if ratio is None or ratio > limit:
                issues.append({"code": "SUPERLINEAR_GROWTH", "case_id": identity,
                               "ratio": _public(ratio) if ratio is not None else None})
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            issues.append({"code": "INVALID_SCALING_MEASUREMENT", "case_id": identity})
    return _outcome(issues)
