"""ARM measurements remain subject to the existing exact absolute budgets."""
from benchmarks import gates, paired


def test_native_arm_measurements_can_certify_and_still_fail_exceeded_budget():
    facts = paired.runtime_for_engine({'Architecture': 'aarch64', 'Name': 'fictional-M4'})
    samples = [{'elapsed_ns': 1000, 'peak_rss_bytes': 1000, 'persisted_bytes': 1000,
                'temp_bytes': 1000, 'exit_code': 0, 'output_hash': 'a' * 64,
                'counts': {'positions': 12}} for _ in range(3)]
    report = {'runner': facts, 'cases': {'P03.activity-append': {'status': 'PASS', 'samples': samples}}}
    contract = [{'id': 'P03.activity-append', 'mode': 'extended_bulk', 'budget_ns': 1000,
                 'budget_stat': 'median'}]
    assert gates.certify(report, contract)['status'] == 'PASS'
    samples[0]['elapsed_ns'] = samples[1]['elapsed_ns'] = 1001
    result = gates.certify(report, contract)
    assert result['status'] == 'FAIL'
    assert any(issue['code'] == 'ABSOLUTE_BUDGET_EXCEEDED' for issue in result['issues'])
