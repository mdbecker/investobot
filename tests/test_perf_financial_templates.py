"""Closed synthetic fixtures reopen in isolated fresh-process observation copies."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks import financial_fixtures, financial_workloads

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def test_base_fixture_closed_copy_hydrates_without_replacing_accepted_facts(tmp_path):
    template = tmp_path / 'template'
    fixture = financial_fixtures.build(template, DIMENSIONS)
    original_hash = fixture.input_state_hash
    original_state = fixture.ledger.planning_state()
    fixture.close()
    assert (template / 'financial-fixture.json').is_file(), 'Persist reconstructable fixture metadata'
    frozen = hashes(template)
    destination = tmp_path / 'observation'
    shutil.copytree(template, destination)
    hydrated = financial_fixtures.build(destination, DIMENSIONS, reuse=True)
    try:
        assert hydrated.input_state_hash == original_hash
        assert hydrated.ledger.path == destination / 'financial.db'
        assert hydrated.frozen == destination / 'frozen.db'
        assert hydrated.ledger.planning_state() == original_state
        hydrated.ledger.connection.execute('DELETE FROM cash_balances')
        hydrated.ledger.connection.commit()
        hydrated.reset()
        assert hydrated.ledger.planning_state() == original_state
    finally:
        hydrated.close()
    assert hashes(template) == frozen


@pytest.mark.parametrize('case_id', [
    'P02.idempotent-reimport', 'P03.corrected-snapshot', 'P04.verify',
    'P04.restore-staging', 'P04.schema-migration', 'P04.manifest-verify',
    'P05.hypothetical-risk', 'P06.budget', 'P07.quarterly-proposal',
    'P08.persist-20-plans', 'P08.compare-20', 'P08.markdown-export',
])
def test_case_template_reconstructs_in_fresh_process_with_same_proofs(tmp_path, case_id):
    template = tmp_path / 'template'
    prepared = financial_workloads.prepare(case_id, template, DIMENSIONS)
    input_hash = prepared.input_state_hash
    counts = prepared.counts.copy()
    prepared.close()
    assert (template / 'financial-workload.json').is_file(), 'Persist case-specific preparation facts'
    original_files = hashes(template)
    outputs = []
    code = '''
import json,sys
from pathlib import Path
from benchmarks.financial_workloads import prepare
p=prepare(sys.argv[1],Path(sys.argv[2]),json.loads(sys.argv[3]),reuse=True)
try:
 result=p.operation()
 proofs=p.verify(result)
 p.reset()
 repeated=p.operation()
 repeated_proofs=p.verify(repeated)
 print(json.dumps(dict(input_hash=p.input_state_hash,counts=p.counts,result=result,
   repeated=repeated,proofs=proofs,repeated_proofs=repeated_proofs),default=str))
finally:p.close()
'''
    for index in range(2):
        destination = tmp_path / f'observation-{index}'
        shutil.copytree(template, destination)
        outcome = subprocess.run([sys.executable, '-c', code, case_id, str(destination),
            json.dumps(DIMENSIONS)], capture_output=True, text=True, check=False,
            env=dict(os.environ, PYTHONPATH=str(ROOT)+os.pathsep+str(ROOT/'src')), timeout=120)
        assert outcome.returncode == 0, outcome.stderr
        payload = json.loads(outcome.stdout)
        assert payload['input_hash'] == input_hash
        assert payload['counts'] == counts
        for proof_set in (payload['proofs'], payload['repeated_proofs']):
            assert proof_set
            assert all(proof['passed'] and proof['expected'] == proof['observed']
                       for proof in proof_set.values()), proof_set
        # Artifact paths legitimately differ between isolated observations.
        outputs.append(json.dumps(payload['result'], sort_keys=True).replace(str(destination), '<root>'))
    assert outputs[0] == outputs[1]
    assert hashes(template) == original_files


def test_reuse_requires_existing_metadata_and_matching_recipe(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError), match='(?i)(metadata|fixture|reuse)'):
        financial_fixtures.build(tmp_path / 'missing', DIMENSIONS, reuse=True)
    assert not (tmp_path / 'missing' / 'financial.db').exists()
    fixture = financial_fixtures.build(tmp_path / 'template', DIMENSIONS)
    fixture.close()
    with pytest.raises(ValueError, match='(?i)(dimension|recipe|profile)'):
        financial_fixtures.build(tmp_path / 'template', dict(DIMENSIONS, positions=14), reuse=True)
