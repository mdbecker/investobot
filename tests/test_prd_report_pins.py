"""Modern saved plans expose their immutable evidence in Markdown exports."""

from invest.reports import render


def test_approved_plan_report_preserves_saved_policy_algorithm_and_observation_pins():
    plan = {'id': 'fictional-plan', 'name': 'Fictional proposal',
        'policy_id': 'reviewed-policy-v1', 'policy': {'version': '1', 'source': 'Reviewed policy'},
        'algorithm_version': 'contribution-first-hifo-1', 'data_environment': 'SYNTHETIC',
        'source_state_hash': 'saved-financial-hash', 'manifest_ids': ['immutable-manifest'],
        'source_state': {'snapshots': [{'id': 'accepted-source', 'account': {'id': 'tax'},
            'source_timestamp': '2026-10-10', 'source_hash': 'reviewed-source-hash'}]},
        'issues': [{'code': 'HUMAN_REVIEW', 'blocks_execution_review': True,
                    'message': 'Review original evidence'}]}
    output = render(plan)
    for saved in ('reviewed-policy-v1', 'contribution-first-hifo-1', 'SYNTHETIC',
                  'immutable-manifest', 'accepted-source', '2026-10-10', 'reviewed-source-hash',
                  'HUMAN_REVIEW'):
        assert saved in output
    assert 'Algorithm: unknown' not in output
    assert output == render(plan)
