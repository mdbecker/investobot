"""Fixed offline replay outcomes; CI never asks an agent to invent campaigns."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fuzz import scenario, triage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/fuzz/campaign.json'


def campaign():
    return json.loads(FIXTURE.read_text())


def invoke(arguments, env=None):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/fuzz.py'), *map(str, arguments)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)


def read_report(directory):
    return json.loads((directory / 'fuzz-report.json').read_text())


def test_one_explicit_adversarial_case_needs_no_campaign_quota_or_history(tmp_path):
    data = campaign()
    data['cases'] = data['cases'][:1]
    assert scenario.validate(data)['status'] == 'VALID'
    source = tmp_path / 'requested.json'
    source.write_text(json.dumps(data))
    output = tmp_path / 'requested-report'
    result = invoke(['run', source, '--output-dir', output])
    assert result.returncode == 0, result.stderr
    report = read_report(output)
    assert len(report['cases']) == 1
    assert report['cases'][0]['saved_fixture']


def test_replay_preserves_seed_financial_result_and_private_ledger(tmp_path):
    protected = tmp_path / 'private.db'
    protected.write_bytes(b'Private ledger must never be opened')
    env = dict(os.environ, INVEST_DB=str(protected), FMP_API_KEY='private-secret')
    output = tmp_path / 'report'
    result = invoke(['run', FIXTURE, '--output-dir', output], env)
    assert result.returncode == 0, result.stderr
    report = read_report(output)
    assert protected.read_bytes() == b'Private ledger must never be opened'
    assert 'private-secret' not in json.dumps(report)
    assert report['synthetic_only'] and report['network'] == 'NONE'
    assert report['source_commit'] and report['dependency_lock_hash']
    for case in report['cases']:
        assert case['expected_result'] == case['observed_result']
        assert case['invariants_passed']
        assert case['input_hash'] and case['saved_fixture'] and case['replay_command']
    case = report['cases'][0]
    replay = invoke(['replay', output / case['saved_fixture'], '--output-dir', tmp_path / 'replay'])
    assert replay.returncode == 0, replay.stderr
    repeated = read_report(tmp_path / 'replay')['cases'][0]
    assert repeated['seed'] == case['seed']
    assert repeated['substantive_output_hash'] == case['substantive_output_hash']


@pytest.mark.parametrize('mutation', ['shell', 'path', 'code', 'oracle', 'records'])
def test_untrusted_data_cannot_become_executable_instructions(mutation):
    case = campaign()['cases'][0]
    if mutation == 'shell':
        case['operations'][0]['name'] = 'shell'
    elif mutation in {'path', 'code'}:
        case['operations'][0]['params'][mutation] = '/data/private.db'
    elif mutation == 'oracle':
        case['invariants'] = ['agent_says_correct']
    else:
        case['records'] = 1000000000000
    assert scenario.validate_case(case)['status'] == 'INVALID'


def test_expected_atomic_rejection_can_be_minimized_and_replayed(tmp_path):
    result = triage.minimize(campaign()['cases'][5])
    assert result['classification'] == 'EXPECTED_REJECTION'
    assert result['clean_reproductions'] == 2
    source = tmp_path / 'minimal.json'
    source.write_text(json.dumps(result['case']))
    process = invoke(['replay', source, '--output-dir', tmp_path / 'replay'])
    assert process.returncode == 0, process.stderr
    case = read_report(tmp_path / 'replay')['cases'][0]
    assert case['before_fingerprint'] == case['after_fingerprint']


def test_timeout_is_unresolved_not_a_confirmed_bug(tmp_path):
    process = invoke(['run', FIXTURE, '--output-dir', tmp_path / 'report',
                      '--case-timeout', '0.000001'])
    assert process.returncode != 0
    report = read_report(tmp_path / 'report')
    assert report['status'] == 'FAILED'
    assert all(case['classification'] == 'ENVIRONMENTAL' for case in report['cases'])
    assert all(case['failure_kind'] == 'TIMEOUT' for case in report['cases'])


def test_independent_financial_oracle_detects_changed_cash():
    from fuzz.oracles import check
    before = {'cash': '100', 'positions': [{'quantity': '10', 'price': '10'}], 'activities': []}
    assert check('financial_conservation', before, copy.deepcopy(before), {})['passed']
    after = copy.deepcopy(before)
    after['cash'] = '101'
    assert not check('financial_conservation', before, after, {})['passed']


def test_workflows_never_launch_ai_fuzz_campaigns():
    yaml = '\n'.join(path.read_text() for path in (ROOT / '.github/workflows').glob('*.y*ml'))
    assert 'scripts/fuzz.py run' not in yaml
    assert not any(key in yaml for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'FUZZ_API_KEY'])


def test_saved_case_json_is_complete_replay_input_without_unused_seed(tmp_path):
    """A reviewed sequence replays from its exact retained JSON, not a fake seed."""
    case = campaign()['cases'][3]
    case.pop('seed', None)
    case['operations'][0]['params']['amount'] = '17.25'
    assert scenario.validate_case(case)['status'] == 'VALID'
    source = tmp_path / 'case.json'
    source.write_text(json.dumps(case))
    result = invoke(['replay', source, '--output-dir', tmp_path / 'report'])
    assert result.returncode == 0, result.stderr
    report = read_report(tmp_path / 'report')
    observed = report['cases'][0]
    assert 'seed' not in observed
    saved = tmp_path / 'report' / observed['saved_fixture']
    assert json.loads(saved.read_text()) == case
    repeated = invoke(['replay', saved, '--output-dir', tmp_path / 'repeated'])
    assert repeated.returncode == 0, repeated.stderr
    assert read_report(tmp_path / 'repeated')['cases'][0]['input_hash'] == observed['input_hash']
