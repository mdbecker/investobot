"""Scaling reports distinguish processed growth from fixed work in larger contexts."""
import pytest

from benchmarks import scaling


@pytest.mark.parametrize('case_id,kind', [
    ('P01.cli-startup', 'context_cardinality'),
    ('P08.show', 'context_cardinality'),
    ('P03.activity-append', 'context_cardinality'),
    ('P14.incremental-ingest', 'context_cardinality'),
    ('P10.recursive-exposure', 'record_growth'),
    ('P11.observation-aggregation', 'record_growth'),
    ('P09.quote-hit', 'bounded_control'),
])
def test_scaling_evidence_identifies_what_actually_grows(case_id, kind):
    assert scaling.evidence_kind(case_id) == kind


def test_exposure_scaling_projects_selected_processed_constituents_not_all_vintages():
    report = {'commit': 'fixed', 'runner': {'machine': 'aarch64'}, 'fixture': {},
              'cases': {'P10.recursive-exposure': {'status': 'PASS', 'samples': [{
                  'elapsed_ns': 200000000, 'counts': {'processed_constituents': 48,
                    'funds': 4, 'constituents_per_fund': 12, 'fund_vintages': 2}}]}}}
    result = scaling.project(report, 'P10.recursive-exposure')
    assert result['cases']['P10.recursive-exposure']['samples'][0]['counts'] == {'logical_records': 48}
    assert report['cases']['P10.recursive-exposure']['samples'][0]['counts']['fund_vintages'] == 2


def test_bounded_quote_control_does_not_inflate_unread_fund_inventory():
    dimensions = {'funds': 4, 'constituents_per_fund': 12, 'positions': 12,
                  'history_years': 10, 'vector_dimensions': 384}
    assert scaling.dimensions('P09.quote-hit', dimensions) == dimensions
