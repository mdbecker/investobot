"""Portable research skills: trusted metadata, discovery and project-local copies."""

import os
import shutil
import tempfile
from pathlib import Path

from invest.models import DomainError

SKILL_VERSION = '1.0.0'
SUPPORTED_SKILLS = {
    'investobot-management-insiders': {
        'skill_version': '1.1.0',
        'description': 'Research management, compensation, SEC insider activity and reported ownership.',
        'research_command': 'research.insiders',
        'schema_version': '1.1',
    },
    'investobot-competitive': {
        'skill_version': '1.0.0',
        'description': 'Research company operating competitors, market overlaps and source-backed financial facts.',
        'research_command': 'research.competitive',
        'schema_version': '1.0',
    },
    'investobot-news': {
        'skill_version': '1.0.1',
        'description': 'Research source-backed company news, catalysts and thesis hypotheses with incremental evidence.',
        'research_command': 'research.news',
        'schema_version': '1.0',
    },
    'investobot-earnings': {
        'description': 'Research company earnings and financial disclosures with verified periods and source evidence.',
        'research_command': 'research.earnings',
        'schema_version': '1.0',
    },
    'investobot-political-contributions': {
        'description': 'Research verified senior executive political contributions and permitted source evidence.',
        'research_command': 'research.political',
        'schema_version': '1.0',
    },
}
AGENT_DIRECTORIES = {'codex': '.agents', 'claude-code': '.claude'}


def _root():
    packaged = Path(__file__).parent / 'bundled_skills'
    return packaged if packaged.exists() else Path(__file__).parents[2] / 'skills'


def _metadata(name):
    if name not in SUPPORTED_SKILLS:
        raise DomainError('Unknown research skill')
    return {'name': name, 'skill_version': SKILL_VERSION, **SUPPORTED_SKILLS[name]}


def _safe_path(path):
    """Check unresolved ancestry; resolving first would hide unsafe symlinks."""
    if '..' in path.parts:
        raise DomainError('Skill paths cannot contain traversal')
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise DomainError('Skill paths cannot contain symlinks')


def _skill_files(name):
    _metadata(name)
    root = _root() / name
    _safe_path(root)
    if not root.is_dir():
        raise DomainError('Bundled research skill is missing', 4)
    files = {}
    for path in sorted(root.rglob('*')):
        _safe_path(path)
        if path.is_dir():
            continue
        if not path.is_file():
            raise DomainError('Skill resources must be regular files')
        relative = path.relative_to(root).as_posix()
        files[relative] = path.read_text(encoding='utf-8')
    if 'SKILL.md' not in files:
        raise DomainError('Bundled research skill has no SKILL.md', 4)
    # Canonical frontmatter is deliberately small; no YAML dependency is needed.
    header = files['SKILL.md'].split('---\n')
    if len(header) < 3 or header[0] or f'name: {name}\n' not in header[1]:
        raise DomainError('Invalid bundled skill frontmatter', 4)
    description = next((line.removeprefix('description: ') for line in header[1].splitlines()
                        if line.startswith('description: ')), '')
    if not description or len(description) > 1024:
        raise DomainError('Invalid bundled skill description', 4)
    return files


def list_skills():
    return {'skills': [_metadata(name) for name in sorted(SUPPORTED_SKILLS)]}


def show_skill(name):
    return {**_metadata(name), 'files': _skill_files(name)}


def _existing_files(root):
    _safe_path(root)
    if not root.exists():
        return {}
    if not root.is_dir():
        raise DomainError('Skill destination must be a directory')
    result = {}
    for path in root.rglob('*'):
        _safe_path(path)
        if path.is_dir():
            continue
        if not path.is_file():
            raise DomainError('Installed skill resources must be regular files')
        result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def install_skills(agent, workspace, confirm=False):
    """Preflight all paths, then atomically replace staged trees with rollback."""
    if agent not in AGENT_DIRECTORIES:
        raise DomainError('Unsupported agent; use codex or claude-code')
    if '..' in Path(workspace).parts:
        raise DomainError('Skill workspace cannot contain traversal')
    workspace = Path(os.path.abspath(Path(workspace)))
    _safe_path(workspace)
    if not workspace.is_dir():
        raise DomainError('Skill workspace must be an existing directory')
    destination = workspace / AGENT_DIRECTORIES[agent] / 'skills'
    _safe_path(destination)
    for path in [destination, destination.parent]:
        if path.exists() and not path.is_dir():
            raise DomainError('Skill destination ancestors must be directories')
    bundles = {name: _skill_files(name) for name in sorted(SUPPORTED_SKILLS)}
    copied, unchanged, changed = [], [], []
    for name, bundle in bundles.items():
        target = destination / name
        current = _existing_files(target)
        modified = False
        for relative, text in bundle.items():
            path = target / relative
            _safe_path(path)
            for parent in path.parents:
                if parent == target:
                    break
                if parent.exists() and not parent.is_dir():
                    raise DomainError('Skill resource ancestors must be directories')
            if path.exists() and not path.is_file():
                raise DomainError('Skill resource destination must be a regular file')
            if current.get(relative) == text.encode('utf-8'):
                unchanged.append(str(path))
            else:
                if relative in current and not confirm:
                    raise DomainError('Installed skill was modified; review and use --confirm to replace')
                copied.append(str(path))
                modified = True
        if modified:
            changed.append(name)
    result = {'agent': agent, 'workspace': str(workspace), 'destination': str(destination),
              'skills': [{'name': name, 'skill_version': _metadata(name)['skill_version']}
                         for name in bundles],
              'copied_files': copied, 'unchanged_files': unchanged}
    if not changed:
        return result
    created_directories = []
    completed, backups = [], []
    try:
        # Staging stays on the workspace filesystem so directory replacements are atomic.
        with tempfile.TemporaryDirectory(prefix='.investobot-skills-', dir=workspace) as staging:
            staging = Path(staging)
            for name in changed:
                target, staged = destination / name, staging / name
                if target.exists():
                    shutil.copytree(target, staged)
                else:
                    staged.mkdir()
                for relative, text in bundles[name].items():
                    path = staged / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding='utf-8')
            for directory in [destination.parent, destination]:
                if not directory.exists():
                    directory.mkdir()
                    created_directories.append(directory)
            try:
                for name in changed:
                    target = destination / name
                    if target.exists():
                        backup = staging / f'{name}.backup'
                        target.rename(backup)
                        backups.append((target, backup))
                    (staging / name).rename(target)
                    completed.append(target)
            except Exception:
                for target in reversed(completed):
                    shutil.rmtree(target)
                for target, backup in reversed(backups):
                    backup.rename(target)
                raise
    except OSError as exc:
        for directory in reversed(created_directories):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        raise DomainError('Unable to install project research skills', 4) from exc
    return result
