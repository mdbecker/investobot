"""Compact JUnit evidence without committing giant repeated tracebacks.

Run in Docker after the frozen red suite. This is test-evidence tooling only.
"""
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('junit', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = ET.parse(args.junit).getroot()
results = []
for case in root.iter('testcase'):
    if 'test_mvp_' not in case.get('classname', ''):
        continue
    failure = case.find('failure')
    error = case.find('error')
    diagnostic = failure if failure is not None else error
    message = diagnostic.get('message', '') if diagnostic is not None else ''
    message = re.sub(r'/tmp/pytest-of-root/[^\s\'\"]+', '<temporary-fixture>', message)
    results.append({'scenario': case.get('name'), 'file': case.get('classname'),
                    'outcome': 'FAILED' if failure is not None else
                               'ERROR' if error is not None else 'PASSED',
                    'diagnostic': message[:1500]})
paths = sorted(set(Path('tests').glob('test_mvp_*_bdd.py')) |
               set(Path('tests/features/mvp').glob('*.feature')) |
               set(Path('tests/fixtures').glob('mvp-*')))
manifest = {'baseline_commit': '5120897e9e5a314ad50fb242ad1496d976549a92',
            'specification_pinned_baseline': {
                'commit': 'd31316c8fbda0c2a5aa27a989c1341bcd1d57a31',
                'tests_passed': 752, 'ruff': 'PASSED'},
            'data_environment': 'SYNTHETIC', 'execution': 'offline Docker',
            'baseline_tests_passed': 862,
            'red_scenarios': results,
            'counts': {outcome: sum(row['outcome'] == outcome for row in results)
                       for outcome in ('FAILED', 'ERROR', 'PASSED')},
            'files': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in paths if path.is_file()}}
args.output.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest['counts']))
