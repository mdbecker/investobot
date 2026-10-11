"""Bake version-pinned extensions at image build time; never invoked at runtime."""

import gzip
import hashlib
import json
import sqlite3
import urllib.request
from pathlib import Path

import duckdb

root = Path('/opt/investobot')
root.mkdir(parents=True, exist_ok=True)
connection = duckdb.connect(':memory:')
platform = connection.execute('PRAGMA platform').fetchone()[0]
version = duckdb.__version__
url = f'https://extensions.duckdb.org/v{version}/{platform}/sqlite_scanner.duckdb_extension.gz'
request = urllib.request.Request(url, headers={'User-Agent': f'DuckDB/v{version}'})
with urllib.request.urlopen(request, timeout=120) as response:
    binary = gzip.decompress(response.read())
extension = root / 'sqlite_scanner.duckdb_extension'
extension.write_bytes(binary)
connection.execute("SET autoinstall_known_extensions=false")
connection.execute("SET autoload_known_extensions=false")
connection.execute("LOAD '/opt/investobot/sqlite_scanner.duckdb_extension'")
extension_version = connection.execute(
    "SELECT extension_version FROM duckdb_extensions() WHERE extension_name='sqlite_scanner'"
).fetchone()[0]
if extension_version != '0c93d61':
    raise RuntimeError('Unexpected pinned DuckDB SQLite extension revision')
connection.close()
vec = root / 'vec0.so'
probe = sqlite3.connect(':memory:')
probe.enable_load_extension(True)
probe.load_extension(str(vec))
probe.enable_load_extension(False)
if probe.execute('SELECT vec_version()').fetchone()[0] != 'v0.1.6':
    raise RuntimeError('Unexpected pinned sqlite-vec version')
probe.close()
runtime = {
    'duckdb_sqlite_extension': {'path': str(extension), 'version': extension_version,
                              'sha256': hashlib.sha256(binary).hexdigest()},
    'sqlite_vec': {'path': str(vec), 'version': '0.1.6',
                   'sha256': hashlib.sha256(vec.read_bytes()).hexdigest()},
}
(root / 'analytics-runtime.json').write_text(json.dumps(runtime, sort_keys=True))
