"""Fresh-process offline measurements; preparation and resets are never timed."""

import hashlib
import json
import math
import os
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     default=str).encode()).hexdigest()


def manifest():
    return json.loads((ROOT / 'benchmarks/cases.json').read_text())


def source_hash():
    checksum = hashlib.sha256()
    for directory in ('src', 'benchmarks', 'scripts', 'fuzz'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                checksum.update(str(path.relative_to(ROOT)).encode())
                checksum.update(path.read_bytes())
    checksum.update((ROOT / 'uv.lock').read_bytes())
    return checksum.hexdigest()


def validate_runtime(runtime):
    safe = (runtime.get('docker') is True and runtime.get('network') == 'none'
            and runtime.get('cpus') == 2 and runtime.get('memory_bytes') == 4 * 1024 ** 3
            and runtime.get('machine') in {'aarch64', 'arm64'}
            and runtime.get('emulated', False) is False
            and runtime.get('engine_machine', runtime.get('machine')) in {'aarch64', 'arm64'})
    return {'status': 'PASS' if safe else 'FAIL',
            'issues': [] if safe else [{'code': 'UNSAFE_RUNTIME'}]}


def runtime():
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return ''
    quota = read('/sys/fs/cgroup/cpu.max').split()
    memory = read('/sys/fs/cgroup/memory.max')
    return {'docker': Path('/.dockerenv').exists(), 'machine': platform.machine(),
            'cpus': int(quota[0]) / int(quota[1]) if quota and quota[0] != 'max' else None,
            'memory_bytes': int(memory) if memory.isdecimal() else None,
            'network': 'none' if not Path('/sys/class/net/eth0').exists() else 'connected',
            'gpu_devices': sorted(str(path) for pattern in ('dri/renderD*', 'nvidia[0-9]*', 'kfd')
                                  for path in Path('/dev').glob(pattern)),
            'embedding_workload': 'prepared synthetic vectors; CPU retrieval'}


def schedule(revisions, observations=7):
    return [revisions[i % len(revisions):] + revisions[:i % len(revisions)]
            for i in range(observations)]


def common_batch_counts(warmups, minimum_ns=200_000_000):
    cases = set.intersection(*(set(rows) for rows in warmups.values()))
    if any(set(rows) != cases for rows in warmups.values()):
        raise ValueError('Warmup inventories differ')
    return {case: max(1, math.ceil(minimum_ns / min(rows[case] for rows in warmups.values())))
            for case in sorted(cases)}


def failed_observation(exit_code, reason):
    return {'status': 'FAIL', 'exit_code': exit_code, 'error': reason}


def coverage():
    from benchmarks.analytics_workloads import SUPPORTED_CASES as analytical
    from benchmarks.financial_workloads import SUPPORTED_CASES as financial
    from benchmarks.gates import validate_inventory
    from invest.contracts import tools_list
    value = manifest()
    classified = {row['command'] for row in value['public_paths']}
    public = tools_list()
    names = {row['name'] for row in public['tools']}
    missing = sorted(names - classified)
    implemented = set(analytical) | set(financial)
    missing_cases = sorted(set(value['required_cases']) - implemented)
    checked = validate_inventory(value, value['public_paths'])
    return {'status': 'FAIL' if missing or missing_cases or checked['status'] == 'FAIL' else 'PASS',
            'runnable_cases': sorted(implemented), 'missing_cases': missing_cases,
            'unclassified_paths': missing, 'classified_paths': sorted(classified),
            'exemptions': [{**row, 'path': row['command']} for row in value['public_paths']
                           if row['performance'] == 'exempt'], 'issues': checked['issues']}


def _bytes(roots):
    total = 0
    for root in roots:
        if root.is_file() and not root.is_symlink():
            total += root.stat().st_size
        elif root.is_dir():
            for path in root.rglob('*'):
                try:
                    if path.is_file() and not path.is_symlink():
                        total += path.stat().st_size
                except FileNotFoundError:
                    pass
    return total


def observe(case, dimensions, root, repetitions=None, warmup=False, reuse=False, template_hash=None):
    if int(case['family'][1:]) <= 8:
        from benchmarks.financial_workloads import prepare
    else:
        from benchmarks.analytics_workloads import prepare
    preparation_started = time.perf_counter_ns()
    prepared = prepare(case['id'], root, dimensions, reuse=reuse)
    preparation_ns = time.perf_counter_ns() - preparation_started
    peak = [0]
    stop = threading.Event()

    def monitor():
        while not stop.wait(.005):
            peak[0] = max(peak[0], _bytes((root,)))

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    elapsed = 0
    reset_ns = 0
    iterations = 0
    output_hash = None
    proofs = None
    try:
        while iterations < (repetitions or 1) or (not repetitions and not warmup
                                                and elapsed < 200_000_000):
            reset_started = time.perf_counter_ns()
            prepared.reset()
            reset_ns += time.perf_counter_ns() - reset_started
            start = time.perf_counter_ns()
            output = prepared.operation()
            encoded = json.dumps(output, sort_keys=True, default=str)
            elapsed += time.perf_counter_ns() - start
            iterations += 1
            proofs = prepared.verify(output)
            if set(proofs) != set(case['invariant']) or any(
                p.get('passed') is not True or p.get('expected') != p.get('observed')
                for p in proofs.values()
            ):
                raise ValueError(f"Incorrect workload output: {case['id']}: {proofs}")
            # Paths are incidental; evidence and every substantive value remain hashed.
            encoded = encoded.replace(str(root), '<WORK>')
            current_hash = hashlib.sha256(encoded.encode()).hexdigest()
            if output_hash is not None and current_hash != output_hash:
                raise ValueError('Repeated frozen input produced different output')
            output_hash = current_hash
        prepared.close()
        persisted = _bytes(prepared.storage_roots)
        peak[0] = max(peak[0], _bytes((root,)))
        return {'elapsed_ns': elapsed, 'batch_repetitions': iterations,
                'preparation_ns': preparation_ns, 'reset_ns': reset_ns,
                'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                'persisted_bytes': persisted, 'temp_bytes': max(0, peak[0] - persisted),
                'input_hash': digest({'case': case['id'], 'dimensions': dimensions,
                                      'financial_state_hash': prepared.input_state_hash,
                                      'seed': manifest()['seed']}),
                'input_state_hash': prepared.input_state_hash, 'output_hash': output_hash,
                'counts': prepared.counts, 'invariant_results': proofs,
                'exit_code': 0, 'fresh_process': True,
                'fixture_reused': reuse, 'template_hash': template_hash}
    finally:
        stop.set()
        watcher.join()
        prepared.close()


def run(suite='pr', profile='medium', case=None, observations=None, batch_repetitions=None, scale=1):
    value = manifest()
    facts = runtime()
    if not facts['docker'] or facts['network'] != 'none':
        raise ValueError('Measurements require offline Docker')
    if profile != 'test' and validate_runtime(facts)['status'] != 'PASS':
        raise ValueError('Release measurements require native ARM64, two CPUs and 4 GiB')
    dimensions = value['profiles'][profile]
    if scale not in {1, 4} or (scale == 4 and not case):
        raise ValueError('Matched scaling requires one case and scale 1 or 4')
    if scale == 4:
        from benchmarks.scaling import dimensions as scaled_dimensions

        dimensions = scaled_dimensions(case, dimensions)
    selected = [row for row in value['cases'] if case is None or row['id'] == case]
    if not selected:
        raise ValueError('Unknown case')
    sha = source_hash()
    report = {'commit': os.environ.get('INVEST_PERF_COMMIT', 'SOURCE_HASH:' + sha),
              'fixture': {'recipe_version': value['recipe_version'], 'seed': value['seed'],
                          'hash': digest({'recipe': value, 'dimensions': dimensions}),
                          'dimensions': dimensions},
              'runner': {**facts, 'profile': profile, 'disposable': True, 'warmups': 1,
                         'source_hash': sha, 'fixture_preparation_in_timing': False,
                         'docker_startup_in_timing': False, 'cache': 'warm process; OS cache unknown',
                         'workspace_removed': False, 'fixture_builds': 0}, 'cases': {}}
    env = {key: val for key, val in os.environ.items()
           if key not in {'INVEST_DB', 'FMP_API_KEY', 'INVEST_PROMPTS'}}
    env.update(INVEST_PROMPTS='/data/prompts', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='invest-perf-') as directory:
        workspace = Path(directory)
        for row in selected:
            count = observations or row['repetitions']['pr' if suite == 'pr' else 'extended']
            samples = []
            template = workspace / (row['id'] + '-template')
            process = subprocess.run([sys.executable, str(ROOT / 'scripts/perf.py'), '_prepare'],
                input=json.dumps({'case': row, 'dimensions': dimensions, 'root': str(template)}),
                capture_output=True, text=True, env=env, timeout=600)
            if process.returncode:
                raise RuntimeError(f"{row['id']}: template preparation: {process.stderr[-8000:]}")
            template_manifest = json.loads(process.stdout)
            report['runner']['fixture_builds'] += 1
            for index in range(count + 1):
                request = {'case': row, 'dimensions': dimensions,
                           'root': str(workspace / f"{row['id']}-{index}"),
                           'template': str(template),
                           'repetitions': batch_repetitions, 'warmup': index == 0}
                try:
                    process = subprocess.run(
                        [sys.executable, str(ROOT / 'scripts/perf.py'), '_worker'],
                        input=json.dumps(request), capture_output=True, text=True, env=env, timeout=600)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError(f"{row['id']}: TIMEOUT (600 seconds)") from exc
                if process.returncode:
                    raise RuntimeError(f"{row['id']}: {process.stderr[-8000:]}")
                sample = json.loads(process.stdout)
                if index:
                    samples.append(sample)
            normalized = [s['elapsed_ns'] / s['batch_repetitions'] for s in samples]
            report['cases'][row['id']] = {'status': 'PASS', 'samples': samples,
                'template': template_manifest,
                'median_ns': statistics.median(normalized), 'max_ns': max(normalized),
                'p95_ns': sorted(normalized)[math.ceil(.95 * len(normalized)) - 1]
                          if len(samples) == 21 else None}
    report['runner']['workspace_removed'] = not workspace.exists()
    report['runner']['measurement_wall_seconds'] = time.monotonic() - started
    return report
