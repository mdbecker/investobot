"""Compile verified sqlite-vec 0.1.6 source for the image's native architecture."""

import hashlib
import io
import subprocess
import tarfile
import urllib.request
from pathlib import Path

url = 'https://github.com/asg017/sqlite-vec/releases/download/v0.1.6/sqlite-vec-0.1.6-amalgamation.tar.gz'
request = urllib.request.Request(url, headers={'User-Agent': 'Investobot-build'})
with urllib.request.urlopen(request, timeout=60) as response:
    archive = response.read()
if hashlib.sha256(archive).hexdigest() != '99b6ec36e9d259d91bd6cb2c053c3a7660f8791eaa66126c882a6a4557e57d6a':
    raise RuntimeError('Pinned sqlite-vec source hash mismatch')
root = Path('/build')
root.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source:
    if set(source.getnames()) != {'sqlite-vec.c', 'sqlite-vec.h'}:
        raise RuntimeError('Unexpected sqlite-vec source files')
    for name in ('sqlite-vec.c', 'sqlite-vec.h'):
        member = source.getmember(name)
        if not member.isfile():
            raise RuntimeError('Nonregular sqlite-vec source')
        (root / name).write_bytes(source.extractfile(member).read())
subprocess.run(['gcc', '-fPIC', '-shared', '-O3', '-I/usr/include',
                str(root / 'sqlite-vec.c'), '-o', str(root / 'vec0.so'), '-lm'], check=True)
