"""Project-local portable skill installation and trust-boundary scenarios."""

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.models import DomainError
from invest.research_skills import install_skills, list_skills, show_skill

scenarios('features/research_skills.feature')


@pytest.fixture
def ctx(tmp_path):
    return {'workspace': tmp_path}


@given("Investobot's bundled research skills")
def bundles(ctx):
    ctx['skills'] = list_skills()['skills']


@when('they are installed for Codex')
def install(ctx):
    ctx['result'] = install_skills('codex', ctx['workspace'])


@then('both portable skills and their references are discoverable')
def discover(ctx):
    names = {'investobot-earnings', 'investobot-political-contributions', 'investobot-news'}
    assert {item['name'] for item in ctx['skills']} == names
    for entry in ctx['skills']:
        assert entry['skill_version'] == '1.0.0'
        skill = show_skill(entry['name'])
        assert skill['files']['SKILL.md'].startswith('---\nname: ' + entry['name'])
        assert '\ndescription: ' in skill['files']['SKILL.md']
        assert 'invest schema' in '\n'.join(skill['files'].values())
        for filename, content in skill['files'].items():
            assert (ctx['workspace'] / '.agents/skills' / entry['name'] / filename).read_text() == content
    assert ctx['result']['copied_files']
    assert not (ctx['workspace'] / '.claude').exists()


@given('a user-modified installed skill exists')
def modified(ctx):
    install_skills('codex', ctx['workspace'])
    ctx['modified'] = ctx['workspace'] / '.agents/skills/investobot-earnings/SKILL.md'
    ctx['modified'].write_text('User instructions\n')
    ctx['before'] = files(ctx['workspace'])


@when('installation is requested without overwrite permission')
def protected(ctx):
    with pytest.raises(DomainError):
        install_skills('codex', ctx['workspace'])


@then('all installed and unrelated files remain unchanged')
def unchanged(ctx):
    assert files(ctx['workspace']) == ctx['before']


def files(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob('*') if path.is_file()}


def test_claude_install_and_identical_reinstall(tmp_path):
    first = install_skills('claude-code', tmp_path)
    before = files(tmp_path)
    second = install_skills('claude-code', tmp_path)
    assert first['copied_files']
    assert not second['copied_files']
    assert second['unchanged_files']
    assert files(tmp_path) == before
    assert not (tmp_path / '.agents').exists()


def test_explicit_confirmation_replaces_modified_bundled_file_only(tmp_path):
    install_skills('codex', tmp_path)
    path = tmp_path / '.agents/skills/investobot-earnings/SKILL.md'
    path.write_text('Changed')
    unrelated = tmp_path / '.agents/skills/unrelated/SKILL.md'
    unrelated.parent.mkdir()
    unrelated.write_text('Keep me')
    install_skills('codex', tmp_path, confirm=True)
    assert path.read_text() == show_skill('investobot-earnings')['files']['SKILL.md']
    assert unrelated.read_text() == 'Keep me'


@pytest.mark.parametrize('unsafe', ['../investobot-earnings', '/tmp/escape', '', 'unknown'])
def test_skill_names_are_registry_keys(unsafe):
    with pytest.raises(DomainError):
        show_skill(unsafe)


@pytest.mark.parametrize('parent', ['.agents', '.agents/skills',
                                     '.agents/skills/investobot-earnings'])
def test_install_rejects_symlink_ancestors_before_writes(tmp_path, parent):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = workspace / parent
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(DomainError):
        install_skills('codex', workspace, confirm=True)
    assert not list(outside.iterdir())
    assert not (workspace / '.agents/skills/investobot-political-contributions').exists()


def test_install_rejects_workspace_symlink(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(DomainError):
        install_skills('codex', link)
    assert not list(workspace.iterdir())


def test_unsafe_destination_file_preflights_all_skills(tmp_path):
    target = tmp_path / '.agents/skills/investobot-political-contributions/SKILL.md'
    target.parent.mkdir(parents=True)
    outside = tmp_path / 'private.md'
    outside.write_text('Private')
    target.symlink_to(outside)
    with pytest.raises(DomainError):
        install_skills('codex', tmp_path, confirm=True)
    assert outside.read_text() == 'Private'
    assert not (tmp_path / '.agents/skills/investobot-earnings').exists()


def test_invalid_agent_never_writes(tmp_path):
    with pytest.raises(DomainError):
        install_skills('../../global', tmp_path)
    assert not list(tmp_path.iterdir())


def test_workspace_traversal_cannot_hide_symlink_ancestor(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(DomainError):
        install_skills('codex', link / '..' / 'workspace')
    assert not list(workspace.iterdir())


def test_custom_skill_resources_survive_confirmed_update(tmp_path):
    install_skills('codex', tmp_path)
    root = tmp_path / '.agents/skills/investobot-earnings'
    custom = root / 'references/local-notes.md'
    custom.write_text('Private user notes')
    (root / 'SKILL.md').write_text('User edit')
    install_skills('codex', tmp_path, confirm=True)
    assert custom.read_text() == 'Private user notes'


def test_install_rolls_back_all_skills_on_replace_failure(tmp_path, monkeypatch):
    install_skills('codex', tmp_path)
    path = tmp_path / '.agents/skills/investobot-earnings/SKILL.md'
    path.write_text('User edit')
    political = tmp_path / '.agents/skills/investobot-political-contributions/SKILL.md'
    political.write_text('Other edit')
    before = files(tmp_path)
    rename = Path.rename

    def fail_second_tree(self, target):
        if self.name == 'investobot-political-contributions' and '.investobot-skills-' in str(self.parent):
            raise OSError('Synthetic replacement failure')
        return rename(self, target)

    monkeypatch.setattr(Path, 'rename', fail_second_tree)
    with pytest.raises(DomainError):
        install_skills('codex', tmp_path, confirm=True)
    assert files(tmp_path) == before
