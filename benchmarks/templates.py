"""Closed, checksummed synthetic fixture trees; each observation gets a private copy."""
import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from benchmarks import runner

MANIFEST = 'template-manifest.json'


def _files(root):
    files = {}
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError('Template contains an unsafe filesystem entry')
        if path.name.endswith(('-wal', '-shm')):
            raise ValueError('Template contains an unclosed SQLite handle')
        if stat.S_ISREG(mode) and path.relative_to(root).as_posix() != MANIFEST:
            checksum = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    checksum.update(block)
            files[path.relative_to(root).as_posix()] = {'sha256': checksum.hexdigest(), 'bytes': path.stat().st_size}
    return files


def create(case, dimensions, root):
    root = Path(root)
    if root.exists():
        raise ValueError('Template destination must be new')
    root.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter_ns()
    from benchmarks.analytics_workloads import prepare as analytical
    from benchmarks.financial_workloads import prepare as financial
    prepare = financial if int(case['family'][1:]) <= 8 else analytical
    # Publication happens only after every live connection has closed.
    prepared = prepare(case['id'], root, dimensions, reuse=False)
    try:
        identity = prepared.input_state_hash
    finally:
        prepared.close()
    value = {'schema_version': 1, 'case': case['id'], 'dimensions': dimensions,
             'source_hash': runner.source_hash(), 'recipe_version': runner.manifest()['recipe_version'],
             'seed': runner.manifest()['seed'], 'input_state_hash': identity,
             'build_count': 1, 'files': _files(root)}
    value['template_hash'] = runner.digest(value)
    value['preparation_ns'] = time.perf_counter_ns() - started
    (root / MANIFEST).write_text(json.dumps(value, sort_keys=True))
    return value


def verify(root, case, dimensions):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (root / MANIFEST).is_symlink():
        raise ValueError('Unsafe template root')
    value = json.loads((root / MANIFEST).read_text())
    if (value.get('case') != case['id'] or value.get('dimensions') != dimensions
            or value.get('source_hash') != runner.source_hash()
            or value.get('recipe_version') != runner.manifest()['recipe_version']
            or value.get('seed') != runner.manifest()['seed'] or value.get('build_count') != 1):
        raise ValueError('Template identity or recipe mismatch')
    content = {key: item for key, item in value.items() if key not in {'template_hash', 'preparation_ns'}}
    if runner.digest(content) != value.get('template_hash') or _files(root) != value.get('files'):
        raise ValueError('Template checksum mismatch')
    return value


def clone(template, destination, case, dimensions):
    template, destination = Path(template), Path(destination)
    value = verify(template, case, dimensions)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Observation destination must be new')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fixture-copy-', dir=destination.parent) as directory:
        staged = Path(directory) / 'input'
        shutil.copytree(template, staged)
        if _files(staged) != value['files']:
            raise ValueError('Template changed during copying')
        os.replace(staged, destination)
    return value
