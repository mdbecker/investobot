"""The release demonstration is an ordered real CLI household/recovery workflow."""

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


def test_disposable_public_cli_release_demonstration_covers_required_workflow(tmp_path):
    transcript = tmp_path / 'fictional-demo-transcript.json'
    result = subprocess.run([sys.executable, 'scripts/demo_unified_mvp.py',
        '--output', str(transcript)], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert json.loads(transcript.read_text()) == report
    assert report['data_environment'] == 'SYNTHETIC'
    assert report['disposable_workspace_removed'] is True
    assert report['external_calls'] == 0
    assert report['financial_state_unchanged_by_hypotheticals'] is True
    assert report['restored_financial_fingerprint'] == report['accepted_financial_fingerprint']
    assert len(report['accepted_financial_fingerprint']) == 64
    assert report['accounts']['taxable']['tax_status'] == 'TAXABLE'
    assert report['accounts']['ira']['tax_status'] == 'TAX_DEFERRED'
    steps = report['steps']
    required = ['import.reject_inconsistent', 'import.accept_taxable', 'import.accept_ira',
        'activity.deposit', 'activity.partial_sale', 'performance.actual', 'policy.approve',
        'tax.budget', 'plan.october_contribution', 'tax.harvest_review',
        'portfolio.nested_exposure', 'research.partial', 'backtest.compare',
        'research.text_search', 'research.semantic_search', 'report.export',
        'db.backup', 'db.verify', 'db.restore']
    indexes = {step['name']: index for index, step in enumerate(steps)}
    assert len(indexes) == len(steps), 'Transcript step identities must be unique'
    assert set(required) <= indexes.keys()
    assert [indexes[name] for name in required] == sorted(indexes[name] for name in required)
    by_name = {step['name']: step for step in steps}
    for step in steps:
        assert step['argv'][0] == 'invest', 'Execute the distributed public CLI for every step'
        assert isinstance(step['output'], (dict, list)), 'Each invocation must return parsed JSON'
        assert isinstance(step['exit_code'], int)
    assert by_name['import.reject_inconsistent']['exit_code'] == 3
    rejected = by_name['import.reject_inconsistent']['output']
    assert 'error' in rejected or rejected.get('status') == 'BLOCKED'
    for name in required[1:]:
        assert by_name[name]['exit_code'] == 0, by_name[name]
    actual = by_name['performance.actual']['output']
    assert actual['mode'] == 'ACTUAL'
    assert 'coverage' in actual and 'issues' in actual
    proposed = by_name['plan.october_contribution']['output']
    assert proposed['executed'] is False
    assert proposed['proposed_actions'], 'The demonstration needs a successful cash-funded plan'
    assert all(action['type'] == 'BUY' for action in proposed['proposed_actions'])
    assert proposed['estimated_tax_budget_consumption'] == '0'
    harvest = by_name['tax.harvest_review']['output']
    assert harvest['wash_sale_certified'] is False
    assert any(issue['code'] in {'HOUSEHOLD_IRA_ACQUISITION_CONFLICT',
        'POTENTIAL_WASH_SALE_CONFLICT', 'HOUSEHOLD_PURCHASE_CONFLICT'} for issue in harvest['issues'])
    exposure = by_name['portfolio.nested_exposure']['output']
    assert exposure['companies'] and exposure['unknown_exposure_value'] is not None
    assert report['nested_exposure_path_depth'] >= 2
    research = by_name['research.partial']['output']
    assert research['status'] in {'PARTIAL', 'REVIEW_REQUIRED'}
    assert research['issues'] and research['coverage']['selected_issuer_scope_complete'] is False
    backtest = by_name['backtest.compare']['output']
    assert backtest['classification'] == 'HYPOTHETICAL'
    assert backtest['comparable'] is True
    assert len(backtest['candidates']) == 2
    for name, method in [('research.text_search', 'FTS5'), ('research.semantic_search', 'HYBRID')]:
        search = by_name[name]['output']
        assert search['method'] == method and search['results']
        assert all(hit['source_url'] and hit['content_hash'] for hit in search['results'])
    assert report['exported_report']['plan_id'] == proposed['id']
    assert report['exported_report']['sha256'] and report['exported_report']['content']
    conservation = report['partial_lot_conservation']
    assert Decimal(conservation['sold_quantity']) > 0
    assert Decimal(conservation['remaining_quantity']) > 0
    assert Decimal(conservation['original_quantity']) == (
        Decimal(conservation['sold_quantity']) + Decimal(conservation['remaining_quantity']))
    assert Decimal(conservation['original_adjusted_basis']) == (
        Decimal(conservation['sold_adjusted_basis']) + Decimal(conservation['remaining_adjusted_basis']))
    assert report['recovery']['archive_verified'] is True
    assert report['recovery']['restored_artifact_hashes_verified'] is True
    assert report['recovery']['restored_corpus_retrievable'] is True
    assert not Path(report['workspace_path']).exists()
