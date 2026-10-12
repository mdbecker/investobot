"""Native paired evidence identifies the actual dimension slice, not its parent."""
from copy import deepcopy

import pytest

from benchmarks import paired, runner, scaling


def identity(definitions, dimensions):
    assert hasattr(paired, 'fixture_identity'), 'Paired evidence lacks dimension-specific fixture identity'
    return paired.fixture_identity(definitions, dimensions)


@pytest.mark.parametrize('profile', ['medium', 'stress'])
def test_fixture_identity_matches_complete_recipe_and_actual_dimensions(profile):
    definitions = runner.manifest()
    dimensions = definitions['profiles'][profile]
    original = deepcopy((definitions, dimensions))
    result = identity(definitions, dimensions)
    assert result == {
        'recipe_version': definitions['recipe_version'],
        'seed': definitions['seed'],
        'hash': runner.digest({'recipe': definitions, 'dimensions': dimensions}),
        'dimensions': dimensions,
    }
    assert (definitions, dimensions) == original


def test_matched_scaling_fixture_hashes_do_not_inherit_stress_hash():
    definitions = runner.manifest()
    medium = definitions['profiles']['medium']
    large = scaling.dimensions('P02.apply', medium)
    fixtures = [identity(definitions, dimensions)
                for dimensions in (medium, large, definitions['profiles']['stress'])]
    assert len({fixture['hash'] for fixture in fixtures}) == 3
    for fixture, dimensions in zip(fixtures, (medium, large, definitions['profiles']['stress'])):
        assert fixture['hash'] == runner.digest({'recipe': definitions, 'dimensions': dimensions})
        assert fixture['dimensions'] == dimensions


def test_fixture_identity_retains_independent_dimension_snapshot():
    definitions = runner.manifest()
    dimensions = dict(definitions['profiles']['medium'])
    original = deepcopy(definitions)
    result = identity(definitions, dimensions)
    retained = deepcopy(result)
    dimensions['positions'] += 1
    assert result == retained
    result['dimensions']['positions'] += 2
    assert result['dimensions']['positions'] != dimensions['positions']
    assert definitions == original


@pytest.mark.parametrize('change', ['seed', 'recipe_version', 'case', 'dimension'])
def test_fixture_identity_changes_with_executable_recipe_or_workload(change):
    definitions = runner.manifest()
    dimensions = dict(definitions['profiles']['medium'])
    before = identity(definitions, dimensions)
    if change == 'seed':
        definitions['seed'] += 1
    elif change == 'recipe_version':
        definitions['recipe_version'] += '-changed'
    elif change == 'case':
        definitions['cases'][0]['budget_ns'] += 1
    else:
        dimensions['positions'] += 1
    after = identity(definitions, dimensions)
    assert after['hash'] != before['hash']
    assert after['hash'] == runner.digest({'recipe': definitions, 'dimensions': dimensions})
