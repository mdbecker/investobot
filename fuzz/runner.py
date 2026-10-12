"""Offline, disposable subprocess execution; no provider or selected private ledger."""
import fcntl
import hashlib
import json
import math
import os
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fuzz import novelty, scenario

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    with Path(path).open('rb') as handle:
        raw = handle.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError('INVALID: input exceeds 20 MiB')
    return json.loads(raw)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as handle:
        temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def offline():
    if not Path('/.dockerenv').exists() or Path('/sys/class/net/eth0').exists():
        raise ValueError('Offline Docker (--network none) is required')


def worker(request):
    limits = request['limits']
    resource.setrlimit(resource.RLIMIT_CPU, (limits['case_cpu_seconds'], limits['case_cpu_seconds']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits['case_disk_bytes'], limits['case_disk_bytes']))
    from fuzz.generators import execute
    result = execute(request['case'], Path(request['root']))
    result['worker_peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return result


def execute_case(case, *, large=False, timeout=None):
    offline()
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('INVALID: timeout must be finite and positive')
    validation = scenario.validate_case(case, large=large)
    if validation['status'] != 'VALID':
        raise ValueError('INVALID: ' + json.dumps(validation))
    limits = validation['limits']
    identity = validation['case_hashes'][0]
    result = dict(identity, expected_result=case['expected_result'], seed=case['seed'],
                  classification='ENVIRONMENTAL', observed_result='UNRESOLVED', exit_code=4,
                  stdout='', stderr='', invariants_passed=False)
    started = time.perf_counter_ns()
    with tempfile.TemporaryDirectory(prefix='invest-fuzz-') as directory:
        root = Path(directory)
        env = {key: os.environ[key] for key in ('PATH', 'INVEST_ANALYTICS_RUNTIME') if key in os.environ}
        env.update(HOME=directory, INVEST_DB=str(root / 'ledger.db'), INVEST_PROMPTS=str(root / 'prompts'),
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONPATH=str(ROOT))
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/fuzz.py'), '_worker'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, cwd=ROOT, start_new_session=True)
        stop = threading.Event()
        peaks = {'rss': 0, 'disk': 0}
        exceeded = []

        def monitor():
            while not stop.wait(.005):
                try:
                    pending, visited, pages = [process.pid], set(), 0
                    while pending:
                        pid = pending.pop()
                        if pid in visited:
                            continue
                        visited.add(pid)
                        try:
                            pages += int(Path(f'/proc/{pid}/statm').read_text().split()[1])
                            pending.extend(map(int, Path(f'/proc/{pid}/task/{pid}/children').read_text().split()))
                        except (OSError, ValueError):
                            pass
                    peaks['rss'] = max(peaks['rss'], pages * os.sysconf('SC_PAGE_SIZE'))
                    peaks['disk'] = max(peaks['disk'], sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink()))
                    reason = 'OOM' if peaks['rss'] > limits['case_memory_bytes'] else 'DISK_LIMIT' if peaks['disk'] > limits['case_disk_bytes'] else None
                    if reason:
                        exceeded.append(reason)
                        os.killpg(process.pid, signal.SIGKILL)
                        return
                except (OSError, ValueError, ProcessLookupError):
                    pass

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        try:
            output, errors = process.communicate(json.dumps({'case': case, 'root': directory, 'limits': limits}),
                timeout=limits['case_wall_seconds'] if timeout is None else timeout)
            if exceeded or process.returncode:
                result.update(failure_kind=exceeded[0] if exceeded else 'CPU_LIMIT' if process.returncode == -signal.SIGKILL else 'WORKER_ERROR', stderr=errors[-65536:])
            else:
                raw = json.loads(output)
                passed = all(row['passed'] for row in raw['invariant_results'].values())
                matched = raw['observed_result'] == case['expected_result']
                classification = ('EXPECTED_REJECTION' if raw['observed_result'] != 'SUCCESS' else 'PASSED') if passed and matched else 'UNCONFIRMED'
                result.update(raw, classification=classification, invariants_passed=passed,
                    substantive_output_hash=scenario.digest(raw['substantive_output']),
                    failure_signature=scenario.digest({'observed_result': raw['observed_result'], 'exit_code': raw['exit_code'],
                        'failed_invariants': sorted(name for name, row in raw['invariant_results'].items() if not row['passed'])}))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            result['failure_kind'] = 'TIMEOUT'
        finally:
            stop.set()
            thread.join()
        result['resources'] = {'elapsed_ns': time.perf_counter_ns() - started,
            'peak_rss_bytes': max(peaks['rss'], result.pop('worker_peak_rss_bytes', 0)),
            'temp_peak_bytes': peaks['disk'], 'db_bytes': sum(p.stat().st_size for p in root.rglob('*.db')),
            'wal_bytes': sum(p.stat().st_size for p in root.rglob('*-wal'))}
        result['limits'] = limits
        for key in ('stdout', 'stderr'):
            result[key] = result[key].replace(directory, '<WORK>')[:65536]
    return result


def report(cases, fixture, output):
    from benchmarks.runner import source_hash
    fingerprint = source_hash()
    value = {'status': 'PASSED' if all(row['classification'] in {'PASSED', 'EXPECTED_REJECTION'} for row in cases) else 'FAILED',
        'cases': cases, 'source_commit': os.environ.get('INVEST_SOURCE_COMMIT', 'SOURCE_HASH:' + fingerprint),
        'dirty_tree_fingerprint': fingerprint, 'dependency_lock_hash': hashlib.sha256((ROOT / 'uv.lock').read_bytes()).hexdigest(),
        'fixture_hash': scenario.digest(fixture), 'network': 'NONE', 'synthetic_only': True,
        'external_requests': 0, 'publishing': 'LOCAL_ONLY'}
    output = Path(output)
    for row, case in zip(cases, fixture.get('cases', [fixture]), strict=True):
        relative = 'cases/' + row['input_hash'] + '.json'
        write_json(output / relative, case)
        row.update(saved_fixture=relative, replay_command=f'python scripts/fuzz.py replay {relative} --output-dir replay')
    write_json(output / 'fuzz-report.json', value)
    (output / 'fuzz-report.md').write_text('# Local synthetic fuzz report\n\n' + value['status'] + '\n\n' + '\n'.join(
        f"- {row['id']}: {row['classification']}" for row in cases) + '\n')
    return value


def run(payload, output, history, *, bootstrap=False, acknowledge_missing=False, large=False, timeout=None):
    validation = scenario.validate(payload, large=large)
    if validation['status'] != 'VALID':
        raise ValueError('INVALID: ' + json.dumps(validation))
    history = Path(history)
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prior = read_json(history) if history.exists() else None
        assessment = novelty.assess(payload, prior, acknowledge_missing=bootstrap or acknowledge_missing, large=large)
        if assessment['status'] != 'ACCEPTED':
            raise ValueError(json.dumps(assessment))
        cases = [execute_case(case, large=large, timeout=timeout) for case in payload['cases']]
        value = report(cases, payload, output)
        retained = novelty.validate_history(prior) if prior is not None else {'schema_version': 1, 'bootstrap': True, 'campaigns': []}
        retained['campaigns'].append({'campaign_id': payload['campaign_id'], 'case_hashes': assessment['case_hashes']})
        write_json(history, retained)
        return value
