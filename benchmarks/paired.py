"""Serial Docker-engine orchestration, using the same harness in three locked images."""

import http.client
import json
import os
import socket
import tempfile
import time
import uuid
from copy import deepcopy
from pathlib import Path

from benchmarks import gates, runner, scaling


def checkpoint(output, state):
    """Atomically retain actual evidence; serialization failure preserves its predecessor."""
    if output is None:
        return
    payload = json.dumps(state, indent=2, allow_nan=False) + '\n'
    output = Path(output)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=output.parent, suffix='.tmp',
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
        descriptor = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fixture_identity(definitions, dimensions):
    """Pin the executable recipe and an independent snapshot of the actual slice."""
    return {'recipe_version': definitions['recipe_version'], 'seed': definitions['seed'],
            'hash': runner.digest({'recipe': definitions, 'dimensions': dimensions}),
            'dimensions': deepcopy(dimensions)}


def measurement_batch(warmups):
    """Target twice the 200ms validity floor; faster repeated calls need headroom."""
    return runner.common_batch_counts(warmups, minimum_ns=400_000_000)


def certification_plan(definitions):
    """Absolute budgets refer to named medium sizes, except 100k-vector workloads."""
    plan = []
    for case in definitions['cases']:
        stat = 'p95' if case['id'] == 'P02.apply' else case['budget_stat']
        observations = max(case['repetitions']['extended'], 21 if stat == 'p95' else 3)
        plan.append({'id': case['id'], 'budget_ns': case['budget_ns'], 'budget_stat': stat,
                     'mode': 'extended_retrieval' if observations == 21 else 'extended_bulk',
                     'observations': observations,
                     'dimensions': dict(definitions['profiles'][
                         'stress' if case['id'].startswith('P14.') else 'medium'])})
    return plan


def certification_report(stress, pairs, definitions):
    """Reuse native observations without substituting stress for named-size evidence."""
    small = {pair['case_id']: pair['small_native'] for pair in pairs}
    report = {'commit': stress['commit'], 'runner': deepcopy(stress['runner']), 'cases': {}}
    for contract in certification_plan(definitions):
        identity = contract['id']
        native = stress if identity.startswith('P14.') else small.get(identity)
        if (not native or native.get('commit') != stress['commit']
                or native.get('runner') != stress['runner']
                or native.get('fixture', {}).get('dimensions') != contract['dimensions']
                or identity not in native.get('cases', {})):
            raise ValueError('Missing or incompatible native absolute-budget evidence: ' + identity)
        case = deepcopy(native['cases'][identity])
        case['fixture_dimensions'] = dict(contract['dimensions'])
        report['cases'][identity] = case
    return report


def scaling_plan(definitions):
    """One candidate revision, medium logical input and its matched fourfold slice."""
    base = definitions['profiles']['medium']
    budgets = {row['id']: row for row in certification_plan(definitions)}
    return [{'case': case, 'small': dict(base),
             'large': scaling.dimensions(case['id'], base),
             'revisions': ['candidate'], 'observations': max(
                 case['repetitions']['extended'], budgets[case['id']]['observations']),
             'evidence_kind': scaling.evidence_kind(case['id']),
             'bounded_control': scaling.evidence_kind(case['id']) == 'bounded_control',
             'reason': (case['id'] + ' consumes fixed-size evidence; ordinary latency/resource gates apply.'
                        if scaling.evidence_kind(case['id']) == 'bounded_control' else
                        'Fourfold ' + scaling.evidence_kind(case['id']) + '; native evidence retained.')}
            for case in definitions['cases']]

# Rebaseline requires a reviewed source change, never an approval field in JSON.
REFERENCE_COMMIT = '7cbf2bed13a0447865403e986662119571217bc6'
REFERENCE_RECIPE_SHA256 = 'b26a21352e5862bace3b03a001233c35cffc7920ed1d3b9c92eaf14eda26cb89'


def runtime_for_engine(info):
    machine = info.get('Architecture')
    if machine not in {'aarch64', 'arm64'}:
        raise ValueError('Performance acceptance requires native ARM64 Docker')
    return {'docker': True, 'machine': machine, 'engine_machine': machine,
            'hardware': info.get('Name', 'unknown'), 'engine_id': info.get('ID', 'unknown'),
            'cpus': 2, 'memory_bytes': 4 * 1024 ** 3, 'network': 'none',
            'documented_laptop_equivalent': True,
            'embedding_workload': 'prepared synthetic vectors; CPU retrieval'}


class Engine(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')


def api(method, path, body=None):
    connection = Engine('localhost', timeout=650)
    encoded = json.dumps(body).encode() if body is not None else None
    connection.request(method, '/v1.44' + path, body=encoded,
                       headers={'Content-Type': 'application/json'})
    response = connection.getresponse()
    payload = response.read()
    status = response.status
    connection.close()
    if status >= 300:
        raise RuntimeError(f'Docker {method} {path}: {status}: {payload[:1000]!r}')
    return json.loads(payload) if payload else {}


def observation(image, commit, host_root, case, dimensions, repetitions=None, warmup=False,
                template=None, prepare=False):
    request = {'case': case, 'dimensions': dimensions, 'root': '/tmp/work',
               'repetitions': repetitions, 'warmup': warmup}
    if prepare:
        request = {'case': case, 'dimensions': dimensions, 'root': '/templates/input'}
    elif template:
        request['template'] = '/templates/input'
    binds = [f'{host_root}:/harness:ro']
    if template:
        binds.append(f'{template}:/templates' + ('' if prepare else ':ro'))
    identity = api('POST', '/containers/create', {
        'Image': image,
        'Cmd': ['/opt/venv/bin/python', '/harness/scripts/perf.py', '_prepare' if prepare else '_worker',
                '--request', json.dumps(request)],
        'Env': [f'INVEST_PERF_COMMIT={commit}', 'INVEST_PROMPTS=/data/prompts',
                'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1'],
        'HostConfig': {'NetworkMode': 'none', 'NanoCpus': 2_000_000_000,
                       'Memory': 4 * 1024 ** 3, 'MemorySwap': 4 * 1024 ** 3,
                       'Binds': binds},
    })['Id']
    try:
        api('POST', f'/containers/{identity}/start')
        result = api('POST', f'/containers/{identity}/wait?condition=not-running')
        connection = Engine('localhost', timeout=30)
        connection.request('GET', f'/v1.44/containers/{identity}/logs?stdout=1&stderr=1')
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        streams = {1: bytearray(), 2: bytearray()}
        while raw:
            if len(raw) < 8:
                raise RuntimeError('Truncated Docker log frame')
            length = int.from_bytes(raw[4:8], 'big')
            streams.setdefault(raw[0], bytearray()).extend(raw[8:8 + length])
            raw = raw[8 + length:]
        if result['StatusCode']:
            state = api('GET', f'/containers/{identity}/json')['State']
            reason = 'OOM' if state.get('OOMKilled') else 'OPERATION_FAILED'
            raise RuntimeError(f"{reason} ({result['StatusCode']}): "
                               + streams[2].decode(errors='replace')[-8000:])
        return json.loads(streams[1])
    finally:
        api('DELETE', f'/containers/{identity}?force=1&v=1')


class FixturePool:
    """Owned Docker volumes, built once per revision/case/dimension and always removed."""

    def __init__(self, images, commits, host_root):
        self.images, self.commits, self.host_root = images, commits, host_root
        self.volumes = {}
        self.evidence = []
        self.preparation_ns = 0

    def get(self, revision, case, dimensions):
        key = (revision, case['id'], runner.digest(dimensions))
        if key not in self.volumes:
            volume = api('POST', '/volumes/create', {'Name': 'invest-perf-' + uuid.uuid4().hex})['Name']
            self.volumes[key] = volume
            manifest = observation(self.images[revision], self.commits[revision], self.host_root,
                                   case, dimensions, template=volume, prepare=True)
            self.preparation_ns += manifest['preparation_ns']
            self.evidence.append({'revision': revision, 'commit': self.commits[revision], **manifest})
        return self.volumes[key]

    def clear(self):
        failures = []
        for key, volume in list(self.volumes.items()):
            try:
                api('DELETE', f'/volumes/{volume}')
                del self.volumes[key]
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise RuntimeError('Owned fixture cleanup failed: ' + '; '.join(failures))


def run(images, commits, host_root, suite='pr', output=None):
    pool = FixturePool(images, commits, host_root)
    state = {'status': 'IN_PROGRESS', 'reports': {}, 'comparisons': []}
    failed = None
    try:
        return _run(images, commits, host_root, suite, output, pool, state)
    except BaseException as error:
        failed = error
        state.update(status='FAIL', failure={'kind': type(error).__name__, 'message': str(error)})
        try:
            checkpoint(output, state)
        except Exception as publication_error:
            state['failure']['publication_error'] = str(publication_error)
        raise
    finally:
        try:
            pool.clear()
        except Exception as cleanup_error:
            if failed is None:
                state.update(status='FAIL', failure={'kind': 'CLEANUP_FAILED', 'message': str(cleanup_error)})
                checkpoint(output, state)
                raise
            state['failure']['cleanup_error'] = str(cleanup_error)
            try:
                checkpoint(output, state)
            except Exception as publication_error:
                state['failure']['publication_error'] = str(publication_error)


def _run(images, commits, host_root, suite, output, pool, state):
    """No dynamic models, network providers or user ledgers enter these containers."""
    required = {'reference', 'base', 'candidate'}
    if set(images) != required or set(commits) != required:
        raise ValueError('Exactly reference, base and candidate images/commits required')
    definitions = runner.manifest()
    metadata = json.loads((runner.ROOT / 'benchmarks/reference.json').read_text())
    import hashlib
    recipe_hash = hashlib.sha256((runner.ROOT / 'benchmarks/cases.json').read_bytes()).hexdigest()
    if (metadata['reference_commit'] != commits['reference']
            or commits['reference'] != REFERENCE_COMMIT
            or metadata['recipe_sha256'] != recipe_hash
            or recipe_hash != REFERENCE_RECIPE_SHA256):
        raise ValueError('Unapproved reference or fixture recipe change')
    info = api('GET', '/info')
    runtime = runtime_for_engine(info)
    for image in images.values():
        if api('GET', f'/images/{image}/json').get('Architecture') != 'arm64':
            raise ValueError('Every revision image must be native ARM64; emulation is excluded')
    dimensions = definitions['profiles']['medium' if suite == 'pr' else 'stress']
    fixture = fixture_identity(definitions, dimensions)
    runtime['cache'] = 'warm process; OS cache unknown'
    reports = {revision: {'commit': commits[revision], 'fixture': fixture,
                         'runner': runtime.copy(), 'cases': {}} for revision in required}
    comparisons = []
    started = time.monotonic()
    measured_ns = 0
    prepared_ns = 0
    scaling_reports = []

    def publish():
        state.update(reports=reports, comparisons=comparisons, scaling_reports=scaling_reports,
            measurement_wall_seconds=time.monotonic() - started,
            timed_operation_seconds=measured_ns / 1_000_000_000,
            fixture_preparation_and_reset_seconds=(prepared_ns + pool.preparation_ns) / 1_000_000_000,
            fixture_templates=pool.evidence, fixture_builds=len(pool.evidence),
            reference_review_status=metadata['approval']['status'])
        checkpoint(output, state)
    publish()

    def capture(revision, case, repetitions=None, warmup=False):
        try:
            return observation(images[revision], commits[revision], host_root, case,
                               dimensions, repetitions, warmup,
                               template=pool.get(revision, case, dimensions))
        except Exception as exc:
            reports[revision]['cases'][case['id']] = {'status': 'FAIL', 'error': str(exc)}
            publish()
            raise
    for case in definitions['cases']:
        count = case['repetitions'][suite]
        warmups = {}
        for revision in ('reference', 'base', 'candidate'):
            sample = capture(revision, case, warmup=True)
            warmups[revision] = {case['id']: sample['elapsed_ns']}
            prepared_ns += sample['preparation_ns'] + sample['reset_ns']
            measured_ns += sample['elapsed_ns']
        batch = measurement_batch(warmups)[case['id']]
        mode = 'pr' if suite == 'pr' else ('extended_retrieval' if count == 21 else 'extended_bulk')
        contract = {'mode': mode, 'required_cases': [case['id']], 'fixture': fixture,
                    'runner': runtime, 'reference_commit': commits['reference'],
                    'reference_hash': recipe_hash, 'expected_reference_hash': metadata['recipe_sha256'],
                    'reproduction_command': f'python scripts/perf.py paired --suite {suite}'}

        def measure(retry=False):
            nonlocal measured_ns, prepared_ns
            samples = {revision: [] for revision in required}
            for order in runner.schedule(['reference', 'base', 'candidate'], count):
                for revision in order:
                    sample = capture(revision, case, batch)
                    samples[revision].append(sample)
                    measured_ns += sample['elapsed_ns']
                    prepared_ns += sample['preparation_ns'] + sample['reset_ns']
            for revision in required:
                result = {'status': 'PASS', 'samples': samples[revision]}
                if retry:
                    reports[revision]['cases'][case['id']]['retry'] = result
                else:
                    reports[revision]['cases'][case['id']] = result

        measure()
        result = gates.compare(reports['candidate'], reports['base'], reports['reference'], contract)
        if result['retry_required']:
            # One bounded cooling interval; original observations remain in reports.
            time.sleep(10)
            measure(retry=True)
            result = gates.compare(reports['candidate'], reports['base'], reports['reference'], contract)
        comparisons.append(result)
        publish()
        pool.clear()
        if measured_ns > (1200 if suite == 'pr' else 3600) * 1_000_000_000:
            raise RuntimeError('Measurement job budget exceeded; preparation/build recorded separately')
    budgets = certification_plan(definitions)
    if suite != 'pr':
        for planned in scaling_plan(definitions):
            case = planned['case']
            pair = {'case_id': case['id'], 'expected_complexity': 'linear',
                    'evidence_kind': planned['evidence_kind'], 'reason': planned['reason'],
                    'bounded_control': planned['bounded_control']}
            warmups = {}
            for size in ('small', 'large'):
                sample = observation(images['candidate'], commits['candidate'], host_root,
                                     case, planned[size], warmup=True,
                                     template=pool.get('candidate', case, planned[size]))
                warmups[size] = {case['id']: sample['elapsed_ns']}
                measured_ns += sample['elapsed_ns']
                prepared_ns += sample['preparation_ns'] + sample['reset_ns']
            batch = measurement_batch(warmups)[case['id']]
            samples = {'small': [], 'large': []}
            for index in range(planned['observations']):
                for size in (('small', 'large') if index % 2 == 0 else ('large', 'small')):
                    sample = observation(images['candidate'], commits['candidate'], host_root,
                                         case, planned[size], batch,
                                         template=pool.get('candidate', case, planned[size]))
                    samples[size].append(sample)
                    measured_ns += sample['elapsed_ns']
                    prepared_ns += sample['preparation_ns'] + sample['reset_ns']
            for size in ('small', 'large'):
                raw = {'commit': commits['candidate'], 'runner': runtime,
                       'fixture': fixture_identity(definitions, planned[size]),
                       'cases': {case['id']: {'status': 'PASS', 'samples': samples[size]}}}
                pair[size] = scaling.project(raw, case['id'])
                pair[size + '_native'] = raw
            scaling_reports.append(pair)
            publish()
            pool.clear()
            if measured_ns > 3600 * 1_000_000_000:
                raise RuntimeError('Extended measurement job budget exceeded during matched scaling')
    scaling_result = gates.compare_scaling([pair for pair in scaling_reports
        if not pair['bounded_control']]) if suite != 'pr' else None
    absolute_report = certification_report(reports['candidate'], scaling_reports, definitions) \
        if suite != 'pr' else None
    certification = gates.certify(absolute_report, budgets) if absolute_report else None
    result = {'status': 'FAIL' if any(row['status'] == 'FAIL' for row in comparisons)
              or (certification and certification['status'] == 'FAIL')
              or (scaling_result and scaling_result['status'] == 'FAIL') else 'PASS',
              'reports': reports, 'comparisons': comparisons, 'certification': certification,
              'absolute_budget_report': absolute_report,
              'scaling': scaling_result, 'scaling_reports': scaling_reports,
              'measurement_wall_seconds': time.monotonic() - started,
              'timed_operation_seconds': measured_ns / 1_000_000_000,
              'fixture_preparation_and_reset_seconds': (prepared_ns + pool.preparation_ns) / 1_000_000_000,
              'fixture_templates': pool.evidence, 'fixture_builds': len(pool.evidence),
              'reference_review_status': metadata['approval']['status']}
    state.update(result)
    checkpoint(output, state)
    return result
