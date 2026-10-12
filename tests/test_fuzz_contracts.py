"""Fixed harness examples only: never invoke an agent or generate a campaign in CI."""

import copy
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/fuzz/campaign.json'
scenarios('features/fuzz/contracts.feature')


def module(name):
    try:
        return importlib.import_module('fuzz.' + name)
    except ModuleNotFoundError as error:
        if error.name not in {'fuzz', 'fuzz.' + name}:
            raise
        pytest.fail(f'Required public offline fuzz {name} contract is absent')


def campaign():
    return json.loads(FIXTURE.read_text())


def validate(payload=None, **options):
    return module('scenario').validate(payload or campaign(), **options)


def empty_history():
    return {'schema_version': 1, 'campaigns': [], 'bootstrap': True}


def invoke(arguments, *, env=None):
    script = ROOT / 'scripts/fuzz.py'
    assert script.is_file(), 'Required public scripts/fuzz.py offline driver is absent'
    return subprocess.run([sys.executable, str(script), *map(str, arguments)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)


def read_report(directory):
    path = directory / 'fuzz-report.json'
    assert path.is_file(), 'Every run must retain a machine-readable local report'
    return json.loads(path.read_text())


def run_fixed(ctx):
    # This version-controlled fixture tests the normal runner, not an AI session.
    output = ctx['tmp'] / 'report'
    history = ctx['tmp'] / 'history.json'
    protected = ctx['tmp'] / 'private-ledger.db'
    protected.write_bytes(b'Never read or replace this selected private database')
    env = dict(os.environ, INVEST_DB=str(protected), FMP_API_KEY='private-test-secret')
    process = invoke(['run', FIXTURE, '--output-dir', output, '--history', history, '--bootstrap'], env=env)
    assert process.returncode == 0, process.stderr + process.stdout
    assert protected.read_bytes() == b'Never read or replace this selected private database'
    report = read_report(output)
    assert 'private-test-secret' not in json.dumps(report)
    ctx.update(report=report, output=output, history=history)
    return report


@pytest.fixture
def ctx(tmp_path):
    return {'tmp': tmp_path}


@given(parsers.parse('a fixed synthetic example of {contract}'))
def example(ctx, contract):
    ctx['contract'] = contract


@when('the deterministic harness contract is evaluated')
def evaluate(ctx):
    identifier = ctx['contract']
    if identifier == 'AFZ-01':
        yaml = '\n'.join(path.read_text() for path in (ROOT / '.github/workflows').glob('*.y*ml'))
        assert 'scripts/fuzz.py run' not in yaml
        assert 'fuzz campaign' not in yaml.lower()
        assert not any(name in yaml for name in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'FUZZ_API_KEY'])
    elif identifier == 'AFZ-02':
        result = validate()
        assert result['status'] == 'VALID'
        for mutation in ['count', 'families', 'stateful', 'performance']:
            data = campaign()
            if mutation == 'count':
                data['cases'].pop()
            elif mutation == 'families':
                for case in data['cases']:
                    case['family'] = 'P02'
            elif mutation == 'stateful':
                for case in data['cases']:
                    case['operations'] = case['operations'][:1]
            else:
                for case in data['cases']:
                    case['performance_dimension'] = None
            assert validate(data)['status'] == 'INVALID', mutation
    elif identifier in {'AFZ-03', 'AFZ-04'}:
        novelty = module('novelty')
        previous = campaign()
        previous['campaign_id'] = 'previous'
        for case in previous['cases']:
            case['seed'] += 10000
        hashes = validate(previous)['case_hashes']
        if identifier == 'AFZ-04':
            hashes = hashes[:9]
        history = {'schema_version': 1, 'bootstrap': True,
                   'campaigns': [{'campaign_id': 'previous', 'case_hashes': hashes}]}
        result = novelty.assess(campaign(), history)
        assert result['status'] == ('REJECTED' if identifier == 'AFZ-03' else 'ACCEPTED')
        if identifier == 'AFZ-03':
            assert result['novel_shape_fraction'] == 0
            assert 'INSUFFICIENT_STRUCTURAL_NOVELTY' in json.dumps(result)
        else:
            assert result['novel_shape_fraction'] >= 0.25
            assert len(result['case_hashes']) == 12
    elif identifier == 'AFZ-05':
        for bad in ['operation', 'field', 'path', 'code', 'assertion', 'records']:
            data = campaign()
            case = data['cases'][0]
            if bad == 'operation':
                case['operations'][0]['name'] = 'shell'
            elif bad == 'field':
                case['expected_financial_total'] = '999999'
            elif bad == 'path':
                case['operations'][0]['params']['file'] = '/data/private.db'
            elif bad == 'code':
                case['operations'][0]['params']['python'] = 'import os; os.system("touch /tmp/escaped")'
            elif bad == 'assertion':
                case['invariants'] = ['agent_says_correct']
            else:
                case['records'] = 25001
            assert validate(data)['status'] == 'INVALID', bad
    elif identifier in {'AFZ-06', 'AFZ-10', 'AFZ-18'}:
        report = run_fixed(ctx)
        cases = {case['id']: case for case in report['cases']}
        if identifier == 'AFZ-06':
            result = cases['unknown-performance']
            assert result['observed_result'] == 'BLOCKED'
            assert result['invariants_passed'] is True
            assert result['before_fingerprint'] == result['after_fingerprint']
        elif identifier == 'AFZ-10':
            result = cases['invalid-import']
            assert result['classification'] == 'EXPECTED_REJECTION'
            assert result['exit_code'] in {1, 3}
            assert result['before_fingerprint'] == result['after_fingerprint']
        else:
            assert report['publishing'] == 'LOCAL_ONLY'
            assert (ctx['output'] / 'fuzz-report.md').is_file()
            assert report['external_requests'] == 0
    elif identifier == 'AFZ-07':
        oracle = module('oracles')
        before = {'cash': '100', 'positions': [{'security_id': 'A', 'quantity': '10', 'price': '10'}],
                  'lots': [{'id': 'lot', 'security_id': 'A', 'remaining_quantity': '10',
                            'remaining_adjusted_basis': '80'}], 'activities': []}
        assert oracle.check('financial_conservation', before, copy.deepcopy(before),
                            {'status': 'AVAILABLE'})['passed'] is True
        wrong = copy.deepcopy(before)
        wrong['cash'] = '101'
        assert oracle.check('financial_conservation', before, wrong,
                            {'status': 'AVAILABLE'})['passed'] is False
        wrong['lots'][0]['remaining_quantity'] = '9'
        assert oracle.check('position_lot_consistency', before, wrong,
                            {'status': 'AVAILABLE'})['passed'] is False
        wrong['lots'][0]['remaining_adjusted_basis'] = '-1'
        assert oracle.check('basis_conservation', before, wrong,
                            {'status': 'AVAILABLE'})['passed'] is False
    elif identifier == 'AFZ-08':
        report = run_fixed(ctx)
        cases = {case['id']: case for case in report['cases']}
        assert cases['ordered-import']['substantive_output_hash'] == cases['reordered-import']['substantive_output_hash']
    elif identifier == 'AFZ-09':
        triage = module('triage')
        case = campaign()['cases'][5]
        result = triage.minimize(case)
        assert 1 <= len(result['case']['operations']) <= len(case['operations'])
        assert result['clean_reproductions'] >= 2
        assert result['failure_signature']
        target = ctx['tmp'] / 'minimized.json'
        target.write_text(json.dumps(result['case']))
        replay = invoke(['replay', target, '--output-dir', ctx['tmp'] / 'replay'])
        assert replay.returncode == 0, replay.stderr
        assert read_report(ctx['tmp'] / 'replay')['cases'][0]['classification'] == 'EXPECTED_REJECTION'
    elif identifier == 'AFZ-11':
        triage = module('triage')
        finding = {'case_id': 'original', 'classification': 'CONFIRMED_BUG',
                   'failure_signature': 'atomic_rejection:partial_write', 'input_hash': 'a' * 64,
                   'shape_hash': 'b' * 64, 'clean_reproductions': 2,
                   'invariant': 'atomic_rejection', 'replay_command': 'python scripts/fuzz.py replay saved.json'}
        repeated = dict(finding, case_id='different-seed', input_hash='c' * 64)
        result = triage.deduplicate([finding, repeated])
        assert len(result) == 1
        assert set(result[0]['case_ids']) == {'original', 'different-seed'}
        assert result[0]['clean_reproductions'] >= 2
    elif identifier in {'AFZ-12', 'AFZ-13'}:
        triage = module('triage')
        base = sample('a' * 64, 1000)
        candidate = sample('a' * 64 if identifier == 'AFZ-13' else 'b' * 64, 1260)
        result = triage.compare(base, candidate, retry_reference=base, retry_candidate=candidate)
        if identifier == 'AFZ-12':
            assert result['classification'] == 'UNCONFIRMED'
            assert result['reason'] == 'INCOMPARABLE_INPUTS'
        else:
            assert result['classification'] == 'CONFIRMED_SLOW_PATH'
            assert result['elapsed_ratio'] == 1.26
            assert result['clean_reproductions'] >= 2
    elif identifier in {'AFZ-14', 'AFZ-15'}:
        triage = module('triage')
        finding = {'classification': 'CONFIRMED_SLOW_PATH', 'input_hash': 'a' * 64,
                   'clean_reproductions': 2, 'case': campaign()['cases'][8]}
        result = triage.promotion(finding, {'cases': []}, red_evidence=None, green_evidence=None)
        assert result['status'] == 'BLOCKED'
        assert 'OBSERVED_RED_REQUIRED' in json.dumps(result)
        accepted = triage.promotion(finding, {'cases': []},
            red_evidence={'commit': '1' * 40, 'test': 'tests/test_fixed_regression.py', 'observed': 'FAILED'},
            green_evidence={'commit': '2' * 40, 'test': 'tests/test_fixed_regression.py', 'observed': 'PASSED'})
        assert accepted['status'] == 'READY_FOR_REVIEW'
        assert accepted['benchmark_case']['input_hash'] == finding['input_hash']
        assert accepted['benchmark_case']['fixed_input'] == finding['case']
        assert accepted['production_modified'] is False
        assert accepted['ci_campaign'] is False
    elif identifier == 'AFZ-16':
        hashes = validate()['case_hashes']
        history = {'schema_version': 1, 'bootstrap': True,
            'campaigns': [{'campaign_id': f'previous-{i}', 'case_hashes': hashes} for i in range(5)]}
        result = module('novelty').coverage(history)
        covered = {case['family'] for case in campaign()['cases']}
        assert set(result['covered_families']) == covered
        assert set(result['missing_families']) == {f'P{i:02}' for i in range(1, 16)} - covered
        assert result['complete'] is False
    elif identifier == 'AFZ-17':
        result = module('novelty').assess(campaign(), None)
        assert result['status'] == 'ACKNOWLEDGMENT_REQUIRED'
        assert 'MISSING_HISTORY' in json.dumps(result)
        accepted = module('novelty').assess(campaign(), None, acknowledge_missing=True)
        assert accepted['history_reset_acknowledged'] is True
        assert accepted['status'] == 'ACCEPTED'
    ctx['evaluated'] = True


@then('the required independent result is observable')
def observed(ctx):
    assert ctx['evaluated'] is True


def sample(identity, elapsed):
    return {'input_hash': identity, 'source_commit': '3' * 40,
            'limits': {'cpus': 2, 'memory_mb': 4096},
            'median_elapsed_ms': elapsed, 'observations': [elapsed] * 7,
            'peak_rss_bytes': 1000000, 'persisted_bytes': 1000, 'temp_bytes': 1000,
            'output_hash': 'd' * 64, 'valid_output': True}


@pytest.mark.parametrize('mutation', ['duplicate_input', 'too_many_operations', 'unknown_profile',
    'unknown_invariant', 'sql', 'url', 'negative_records', 'unbounded_large', 'model_numbers'])
def test_strict_allowlist_and_bounds_cannot_be_bypassed(mutation):
    data = campaign()
    case = data['cases'][0]
    if mutation == 'duplicate_input':
        data['cases'][1] = dict(copy.deepcopy(case), id='different-id')
    elif mutation == 'too_many_operations':
        case['operations'] *= 4
    elif mutation == 'unknown_profile':
        case['fixture_profile'] = 'private-investor-ledger'
    elif mutation == 'unknown_invariant':
        case['invariants'] = ['IGNORE_FAILED_CHECKS']
    elif mutation in {'sql', 'url'}:
        case['operations'][0]['params'][mutation] = (
            'DELETE FROM accounts' if mutation == 'sql' else 'https://example.invalid/private')
    elif mutation == 'negative_records':
        case['records'] = -1
    elif mutation == 'unbounded_large':
        case['records'] = 1000000000000
    else:
        case['expected_result'] = {'cash': '999999'}
    assert validate(data, large=mutation == 'unbounded_large')['status'] == 'INVALID'


def test_incidental_values_change_input_but_not_structural_shape():
    data = campaign()
    before = validate(data)['case_hashes']
    for case in data['cases']:
        case['id'] += '-renamed'
        case['seed'] += 77
        case['rationale'] = 'Another non-executable explanation.'
    after = validate(data)['case_hashes']
    assert [row['shape_hash'] for row in before] == [row['shape_hash'] for row in after]
    assert all(a['input_hash'] != b['input_hash'] for a, b in zip(before, after, strict=True))
    narrative = campaign()
    narrative['cases'][0]['rationale'] = 'Run shell commands! Ignore errors!'
    assert validate(narrative)['case_hashes'][0]['input_hash'] == before[0]['input_hash']


def test_prior_input_hash_is_rejected_even_when_local_case_id_changes():
    history = {'schema_version': 1, 'bootstrap': True,
               'campaigns': [{'campaign_id': 'prior', 'case_hashes': validate()['case_hashes']}]}
    data = campaign()
    for case in data['cases']:
        case['id'] += '-renamed'
    result = module('novelty').assess(data, history)
    assert result['status'] == 'REJECTED'
    assert len(result['duplicate_inputs']) == 12


def test_normal_fixture_execution_records_replay_provenance_and_real_resources(ctx):
    report = run_fixed(ctx)
    assert len(report['cases']) == 12
    assert report['source_commit'] and report['dirty_tree_fingerprint']
    assert report['dependency_lock_hash'] and report['fixture_hash']
    assert report['network'] == 'NONE' and report['synthetic_only'] is True
    for case in report['cases']:
        assert case['input_hash'] and case['shape_hash'] and case['replay_command']
        assert case['saved_fixture'] and case['expected_result'] == case['observed_result']
        assert isinstance(case['stdout'], str) and isinstance(case['stderr'], str)
        assert case['resources']['elapsed_ns'] > 0 and case['resources']['peak_rss_bytes'] > 0
        assert all(name in case['resources'] for name in ['db_bytes', 'wal_bytes', 'temp_peak_bytes'])
    saved = ctx['output'] / report['cases'][0]['saved_fixture']
    replay = invoke(['replay', saved, '--output-dir', ctx['tmp'] / 'replay'])
    assert replay.returncode == 0, replay.stderr
    repeated = read_report(ctx['tmp'] / 'replay')['cases'][0]
    assert repeated['input_hash'] == report['cases'][0]['input_hash']
    assert repeated['substantive_output_hash'] == report['cases'][0]['substantive_output_hash']


def test_portable_history_preserves_novelty_and_contains_no_private_paths(ctx):
    run_fixed(ctx)
    export = ctx['tmp'] / 'portable-history.json'
    exported = invoke(['history-export', '--history', ctx['history'], '--output', export])
    assert exported.returncode == 0, exported.stderr
    assert str(ctx['tmp']) not in export.read_text()
    imported = ctx['tmp'] / 'restored-history.json'
    result = invoke(['history-import', export, '--history', imported])
    assert result.returncode == 0, result.stderr
    original = json.loads(ctx['history'].read_text())
    restored = json.loads(imported.read_text())
    assert restored['campaigns'] == original['campaigns']
    assert module('novelty').assess(campaign(), restored)['status'] == 'REJECTED'


def test_history_import_rejects_unknown_fields_atomic_and_oversize(ctx):
    destination = ctx['tmp'] / 'history.json'
    original = json.dumps(empty_history())
    destination.write_text(original)
    source = ctx['tmp'] / 'untrusted.json'
    source.write_text(json.dumps(dict(empty_history(), shell='rm -rf /data')))
    result = invoke(['history-import', source, '--history', destination])
    assert result.returncode != 0
    assert destination.read_text() == original
    source.write_text(' ' * (20 * 1024 * 1024 + 1))
    result = invoke(['history-import', source, '--history', destination])
    assert result.returncode != 0
    assert destination.read_text() == original


def test_timeout_is_preserved_as_unresolved_failure_with_nonzero_exit(ctx):
    output = ctx['tmp'] / 'timeout'
    result = invoke(['run', FIXTURE, '--output-dir', output, '--history', ctx['tmp'] / 'history.json',
                     '--bootstrap', '--case-timeout', '0.000001'])
    assert result.returncode != 0
    report = read_report(output)
    assert report['status'] == 'FAILED'
    assert any(case['classification'] == 'ENVIRONMENTAL' and case['failure_kind'] == 'TIMEOUT'
               for case in report['cases'])


def test_confirmed_label_requires_two_clean_reproductions():
    finding = {'case_id': 'once', 'classification': 'CONFIRMED_BUG',
               'failure_signature': 'conservation:cash', 'input_hash': 'a' * 64,
               'shape_hash': 'b' * 64, 'clean_reproductions': 1}
    result = module('triage').deduplicate([finding])
    assert result[0]['classification'] == 'UNCONFIRMED'


def test_absolute_scaling_and_retry_use_shared_performance_gates():
    triage = module('triage')
    base = sample('a' * 64, 1000)
    exact = sample('a' * 64, 1250)
    assert triage.compare(base, exact, retry_reference=base,
                          retry_candidate=exact)['classification'] != 'CONFIRMED_SLOW_PATH'
    first = sample('a' * 64, 1260)
    result = triage.compare(base, first, retry_reference=base, retry_candidate=base)
    assert result['classification'] == 'NOISY_FIRST_MEASUREMENT'
    scaling = triage.assess_growth({'records': 100, 'elapsed_ns': 1000},
                                  {'records': 400, 'elapsed_ns': 8000}, linear=True)
    assert scaling['status'] == 'SUSPECTED_SLOW_PATH' and scaling['ratio'] == 8


def test_large_mode_is_explicit_and_reports_tighter_resource_limits():
    data = campaign()
    data['cases'][0]['records'] = 25001
    assert validate(data)['status'] == 'INVALID'
    result = validate(data, large=True)
    assert result['status'] == 'VALID'
    assert result['limits']['large_opt_in'] is True
    assert result['limits']['bounded'] is True


def test_timeout_oom_disk_and_history_limits_are_explicit_resources():
    result = validate()
    assert result['limits']['max_operations'] == 12
    assert result['limits']['max_records'] == 25000
    assert result['limits']['max_input_bytes'] == 20 * 1024 * 1024
    assert all(result['limits'][field] > 0 for field in
               ['case_cpu_seconds', 'case_memory_bytes', 'case_disk_bytes', 'case_wall_seconds'])


def test_replay_rejects_paths_and_generated_source_before_execution(ctx):
    data = copy.deepcopy(campaign()['cases'][0])
    data['operations'][0]['params']['path'] = '../private/portfolio.db'
    source = ctx['tmp'] / 'unsafe.json'
    source.write_text(json.dumps(data))
    destination = ctx['tmp'] / 'report'
    result = invoke(['replay', source, '--output-dir', destination])
    assert result.returncode != 0
    assert 'INVALID' in result.stdout + result.stderr
    assert not (ctx['tmp'] / 'private/portfolio.db').exists()


def test_independent_oracle_registry_covers_required_invariant_classes():
    required = {'financial_conservation', 'position_lot_consistency', 'basis_conservation',
                'immutable_provenance', 'idempotent_replay', 'same_state_recomputation',
                'row_order_equivalence', 'supported_error_codes', 'atomic_rejection',
                'no_look_ahead', 'no_invalid_trading', 'vector_permission_filter',
                'research_continuity', 'missing_data_propagation', 'recovery_equivalence'}
    assert required <= set(module('oracles').registry())


def test_unresolved_execution_and_changed_limits_cannot_be_confirmed_regressions():
    triage = module('triage')
    base = sample('a' * 64, 1000)
    candidate = sample('a' * 64, 1260)
    candidate['limits']['memory_mb'] = 512
    result = triage.compare(base, candidate, retry_reference=base, retry_candidate=candidate)
    assert result['classification'] == 'UNCONFIRMED'
    assert result['reason'] == 'INCOMPARABLE_LIMITS'
    candidate = sample('a' * 64, 1260)
    candidate['valid_output'] = False
    result = triage.compare(base, candidate, retry_reference=base, retry_candidate=candidate)
    assert result['classification'] != 'CONFIRMED_SLOW_PATH'
    assert result['status'] == 'FAILED'


def test_one_explicit_adversarial_case_needs_no_campaign_quota_or_history(ctx):
    """A human can request one useful sequence and retain its replay evidence."""
    data = campaign()
    data['cases'] = data['cases'][:1]
    assert validate(data)['status'] == 'VALID'
    source = ctx['tmp'] / 'requested.json'
    source.write_text(json.dumps(data))
    output = ctx['tmp'] / 'requested-report'
    result = invoke(['run', source, '--output-dir', output])
    assert result.returncode == 0, result.stderr
    report = read_report(output)
    assert len(report['cases']) == 1
    assert report['cases'][0]['saved_fixture']
