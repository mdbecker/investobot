"""Discovered JSON contracts must expose the actual public validation models."""

import hashlib
import json

import pytest
from test_prd_research_audit import specialty_package

from invest.analytics_store import ManifestInput
from invest.contracts import tools_describe
from invest.research_storage import SPECIALTIES, ResearchEnvelope
from invest.tax_policy import HarvestReviewPolicy


@pytest.mark.parametrize('command', ['data.snapshot', 'data.verify'])
def test_dataset_commands_publish_authoritative_manifest_schema(command):
    rows = [{'security_id': 'fictional', 'weight': '1'}]
    payload = {'id': 'fictional-snapshot', 'purpose': 'PUBLIC_DATASET',
        'data_environment': 'SYNTHETIC', 'artifacts': [{'id': 'fictional-table',
            'kind': 'HOLDINGS', 'rows': rows,
            'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()}]}
    model = ManifestInput.model_validate(payload)
    assert model.data_environment == 'SYNTHETIC'
    schema = tools_describe(command)['json_input_schema']
    assert schema == ManifestInput.model_json_schema()
    assert schema['additionalProperties'] is False
    assert 'ArtifactInput' in schema['$defs']


def test_harvest_command_publishes_typed_review_policy_schema():
    payload = {'loss_sale_date': '2026-10-10', 'security': 'fictional-canonical-security',
        'data_environment': 'SYNTHETIC', 'spouse_history_complete': False,
        'outside_account_history_complete': False, 'dividend_reinvestment_history_complete': None}
    HarvestReviewPolicy.model_validate(payload)
    schema = tools_describe('tax.harvest-plan')['json_input_schema']
    assert schema == HarvestReviewPolicy.model_json_schema()
    assert schema['additionalProperties'] is False
    assert schema['properties']['loss_sale_date']['format'] == 'date'


def schema_objects(value):
    """Inspect published schema branches without implementing a second validator."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_objects(child)


@pytest.mark.parametrize('kind', ['NEWS', 'EARNINGS', 'COMPETITIVE', 'INSIDERS', 'POLITICAL'])
def test_native_import_contract_exposes_strict_common_envelope_branch(kind):
    package = specialty_package(kind)
    as_of = package.get('researched_as_of') or package['scope']['researched_as_of']
    payload = {'kind': kind, 'issuer_id': '0000000001', 'as_of': as_of,
        'data_environment': 'SYNTHETIC', 'skill_name': SPECIALTIES[kind][1], 'package': package}
    ResearchEnvelope.model_validate(payload)
    schema = tools_describe('research.' + SPECIALTIES[kind][0].replace('_', '-') + '.import')[
        'json_input_schema']
    expected = ResearchEnvelope.model_json_schema()
    branches = list(schema_objects(schema))
    assert any(branch.get('properties') == expected['properties'] and
               branch.get('required') == expected['required'] and
               branch.get('additionalProperties') is False for branch in branches), (
                   'Native import accepts the shared envelope, so discovery must expose its strict '
                   'issuer, environment, kind, skill and package constraints')


@pytest.mark.parametrize('command', ['backtest.run', 'backtest.compare'])
def test_backtest_file_contract_exposes_real_history_and_assumption_fields(command):
    schema = tools_describe(command)['json_input_schema']
    branches = list(schema_objects(schema))
    required_fields = {'start', 'end', 'candidates', 'history', 'history_provenance',
                       'cash_return', 'fees', 'starting_value', 'rebalancing'}
    assert any(required_fields <= set(branch.get('properties', {})) for branch in branches), (
        'Documented hypothetical history payload cannot be represented by a closed empty object')
    assert any(branch.get('properties', {}).get('data_environment', {}).get('enum') ==
               ['REAL', 'SYNTHETIC'] for branch in branches), (
                   'History provenance must expose the accepted source environments')
