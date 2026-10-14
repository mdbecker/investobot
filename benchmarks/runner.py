"""Fixed offline workflows with native output oracles outside measurement time."""
import hashlib
import json
import math
import os
import platform
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def manifest():
    return json.loads((ROOT / 'cases.json').read_text())


def recipes():
    return manifest()['workflows']


def recipe_hash():
    return hashlib.sha256((ROOT / 'cases.json').read_bytes()).hexdigest()


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
            'engine_machine': os.environ.get('INVEST_PERF_ENGINE_ARCH'),
            'engine_id': os.environ.get('INVEST_PERF_ENGINE_ID'),
            'image_machine': os.environ.get('INVEST_PERF_IMAGE_ARCH')}


def validate_runtime(facts):
    valid = (facts.get('docker') is True and facts.get('network') == 'none'
             and facts.get('machine') in {'arm64', 'aarch64'}
             and not facts.get('emulated')
             and facts.get('engine_machine', facts.get('machine')) in {'arm64', 'aarch64'}
             and facts.get('cpus') == 2 and facts.get('memory_bytes') == 4 * 1024 ** 3)
    return {'status': 'PASS' if valid else 'FAIL', 'issues': [] if valid else ['UNSAFE_RUNTIME']}


def common_batch_counts(reference, candidate):
    if reference['recipe_hash'] != candidate['recipe_hash'] or reference['runner'] != candidate['runner']:
        raise ValueError('Warmup recipe or runner differs')
    a, b = reference['cases'], candidate['cases']
    if len(a) != 8 or set(a) != set(b):
        raise ValueError('Warmup requires eight matching workflows')
    counts = {}
    for name in a:
        if any(a[name][key] != b[name][key] for key in ('input_hash', 'output_hash', 'counts')):
            raise ValueError('Warmup native workflow evidence differs')
        fastest = min(a[name]['warmup_ns'], b[name]['warmup_ns'])
        if fastest <= 0:
            raise ValueError('Warmup duration must be positive')
        # A single cold warmup may run slower than a warmed batch. This margin
        # avoids interpreting short samples as evidence; the strict floor stays 200 ms.
        counts[name] = max(1, math.ceil(600_000_000 / fastest))
    return {'recipe_hash': reference['recipe_hash'], 'batches': counts}


def measure(revision, *, batches=None):
    """Prepare fresh inputs; reset, verification and cleanup are outside timed calls."""
    facts = runtime()
    if (validate_runtime(facts)['status'] != 'PASS' or not facts['engine_id']
            or facts['image_machine'] not in {'arm64', 'aarch64'}):
        raise ValueError('Measurements require native ARM Docker, offline, 2 CPUs and 4 GiB')
    if batches and (batches.get('recipe_hash') != recipe_hash()
                    or set(batches.get('batches', {})) != {row['id'] for row in recipes()}):
        raise ValueError('Batch recipe or inventory differs')
    from benchmarks.analytics_workloads import prepare as analytical
    from benchmarks.financial_workloads import prepare as financial
    report = {'revision': revision, 'recipe_hash': recipe_hash(), 'runner': facts, 'cases': {}}
    with tempfile.TemporaryDirectory(prefix='investobot-performance-') as temporary:
        for workflow in recipes():
            prepared = []
            try:
                for operation in workflow['operations']:
                    prepare = financial if int(operation.split('.')[0][1:]) <= 8 else analytical
                    definitions = manifest()
                    dimensions = definitions['profiles'][definitions['profile']]
                    prepared.append(prepare(operation, Path(temporary) / operation, dimensions))
                count = batches['batches'][workflow['id']] if batches else 1
                if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                    raise ValueError('Positive integral batch required')
                elapsed_samples, output_hash = [], None
                for _sample in range(5 if batches else 1):
                    elapsed = 0
                    for _iteration in range(count):
                        results = []
                        for operation in prepared:
                            operation.reset()
                            start = time.perf_counter_ns()
                            result = operation.operation()
                            elapsed += time.perf_counter_ns() - start
                            proofs = operation.verify(result)
                            if not proofs or not all(proof['passed'] for proof in proofs.values()):
                                raise ValueError(f'Native oracle failed: {workflow["id"]}: {proofs}')
                            results.append(result)
                        from benchmarks.correctness_projection import project
                        observed = digest(project(results))
                        if output_hash is not None and observed != output_hash:
                            raise ValueError('Repeated workflow output differs')
                        output_hash = observed
                    elapsed_samples.append(elapsed)
                row = {'input_hash': digest([op.input_state_hash for op in prepared]),
                       'output_hash': output_hash,
                       'counts': {name: op.counts for name, op in zip(workflow['operations'], prepared, strict=True)}}
                if batches:
                    row.update(batch=count, samples_ns=elapsed_samples)
                else:
                    row['warmup_ns'] = elapsed_samples[0]
                for operation in prepared:
                    operation.close()
                prepared.clear()
                report['cases'][workflow['id']] = row
            finally:
                for operation in prepared:
                    operation.close()
    return report
