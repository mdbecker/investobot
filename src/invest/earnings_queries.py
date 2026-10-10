"""Read saved earnings facts and compare only compatible reported observations."""

import json
from datetime import date
from decimal import Decimal, Inexact, localcontext

from invest.models import DomainError

RESEARCH_TYPE = 'EARNINGS_FINANCIAL_STATEMENTS'
RUN_COLUMNS = ('id', 'skill_name', 'skill_version', 'schema_version', 'company_name',
               'ticker', 'security_id', 'cik', 'fiscal_year', 'fiscal_period',
               'period_end', 'researched_as_of', 'imported_at', 'coverage_status', 'summary_json')
METRIC_COLUMNS = ('metric_id', 'metric_code', 'metric_label', 'metric_definition',
                  'value_text', 'unit', 'accounting_basis', 'period_type', 'period_length',
                  'period_start', 'period_end', 'fiscal_year', 'fiscal_period',
                  'measurement_type', 'scope', 'segment_name', 'source_id', 'source_locator',
                  'xbrl_taxonomy', 'xbrl_concept')
COMPATIBILITY_KEYS = ('metric_code', 'metric_definition', 'unit', 'accounting_basis',
                      'period_type', 'period_length', 'fiscal_period', 'measurement_type',
                      'scope', 'segment_name', 'xbrl_taxonomy', 'xbrl_concept')


def _runs(ledger, where='', parameters=()):
    return [dict(zip(RUN_COLUMNS, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(RUN_COLUMNS)} FROM research_runs "
        f'WHERE research_type=? {where} ORDER BY imported_at DESC, id DESC',
        (RESEARCH_TYPE, *parameters))]


def _run(ledger, run_id):
    rows = _runs(ledger, 'AND id=?', (run_id,))
    if not rows:
        raise DomainError('Unknown earnings research run', 1)
    return rows[0]


def _metadata(row):
    return {'research_run_id': row['id'], **{key: value for key, value in row.items()
                                           if key not in {'id', 'summary_json'}}}


def list_runs(ledger, ticker=None):
    rows = _runs(ledger, 'AND UPPER(ticker)=UPPER(?)' if ticker is not None else '',
                 (ticker,) if ticker is not None else ())
    return {'runs': [{**json.loads(row['summary_json']), **_metadata(row)} for row in rows]}


def show(ledger, run_id):
    row = ledger.connection.execute(
        '''SELECT package_json, skill_name, skill_version, imported_at FROM research_runs
           WHERE id=? AND research_type=?''', (run_id, RESEARCH_TYPE)).fetchone()
    if row is None:
        raise DomainError('Unknown earnings research run', 1)
    return {**json.loads(row[0]), 'research_run_id': run_id, 'skill_name': row[1],
            'skill_version': row[2], 'imported_at': row[3]}


def _metrics(ledger, run_id):
    rows = []
    for values in ledger.connection.execute(
        f"SELECT {', '.join(METRIC_COLUMNS)} FROM research_earnings_metrics "
        'WHERE run_id=? ORDER BY metric_id', (run_id,)):
        row = dict(zip(METRIC_COLUMNS, values, strict=True))
        row['id'] = row.pop('metric_id')
        row['value'] = row.pop('value_text')
        row['fiscal_year'] = int(row['fiscal_year'])
        rows.append(row)
    return rows


def _amendment_warnings(ledger, run_id):
    return [f'Amended/restated source {source_id} preserves original accession {original}.'
            for source_id, original in ledger.connection.execute(
                '''SELECT source_id, original_accession_number FROM research_sources
                   WHERE run_id=? AND (is_amendment=1 OR is_restatement=1)
                   ORDER BY source_id''', (run_id,))]


def _warnings(ledger, row):
    warnings = list(json.loads(row['summary_json']).get('warnings', []))
    warnings.extend(_amendment_warnings(ledger, row['id']))
    return list(dict.fromkeys(warnings))


def summary(ledger, run_id):
    row = _run(ledger, run_id)
    warnings = _warnings(ledger, row)
    warnings.append('Insufficient verified comparable periods for year-over-year growth; '
                    'use compare with explicitly selected saved runs.')
    counts = {}
    for table, key in (('guidance', 'guidance_count'), ('findings', 'findings_count')):
        counts[key] = ledger.connection.execute(
            f'SELECT COUNT(*) FROM research_earnings_{table} WHERE run_id=?',
            (run_id,)).fetchone()[0]
    return {**_metadata(row), 'company': row['company_name'],
            'metrics': _metrics(ledger, run_id), **counts,
            'year_over_year_growth': None, 'warnings': warnings}


def _same_company(first, second):
    # Strong identifiers must never contradict, even when another identifier agrees.
    for key in ('cik', 'security_id'):
        if first[key] and second[key] and first[key] != second[key]:
            return False
    if first['cik'] and second['cik']:
        return first['cik'] == second['cik']
    if first['security_id'] and second['security_id']:
        return first['security_id'] == second['security_id']
    return bool(first['ticker'] and second['ticker'] and
                first['ticker'].casefold() == second['ticker'].casefold() and
                first['company_name'].casefold() == second['company_name'].casefold())


def _duration(metric):
    if metric['period_type'] == 'INSTANT':
        return None
    return (date.fromisoformat(metric['period_end']) -
            date.fromisoformat(metric['period_start'])).days + 1


def _compatible(first, second):
    return all(first[key] == second[key] for key in COMPATIBILITY_KEYS) and \
        _duration(first) == _duration(second)


def _precision(first, second):
    exponent = min(first.as_tuple().exponent, second.as_tuple().exponent)
    integer_digits = max(first.adjusted(), second.adjusted()) + 1
    return max(64, integer_digits - exponent + 4,
               len(first.as_tuple().digits) + len(second.as_tuple().digits) + 16)


def compare(ledger, run_a, run_b):
    first_run, second_run = _run(ledger, run_a), _run(ledger, run_b)
    first_metrics, second_metrics = _metrics(ledger, run_a), _metrics(ledger, run_b)
    warnings = _warnings(ledger, first_run) + _warnings(ledger, second_run)
    same_company = _same_company(first_run, second_run)
    if not same_company:
        warnings.append('Incompatible reporting entities; company identity does not match.')
    comparisons = []
    for first in first_metrics:
        same_code = [second for second in second_metrics
                     if second['metric_code'] == first['metric_code']]
        matching = [second for second in same_code if _compatible(first, second)]
        second = matching[0] if len(matching) == 1 else (
            same_code[0] if len(same_code) == 1 else None)
        result = {'metric_code': first['metric_code'], 'metric_definition': first['metric_definition'],
                  'accounting_basis': first['accounting_basis'], 'unit': first['unit'],
                  'scope': first['scope'], 'segment_name': first['segment_name'],
                  'run_a_metric_id': first['id'], 'run_b_metric_id': second['id'] if second else None,
                  'value_a': first['value'], 'value_b': second['value'] if second else None,
                  'source_a_id': first['source_id'],
                  'source_b_id': second['source_id'] if second else None,
                  'absolute_change': None, 'percentage_change': None}
        if not same_company or second is None or len(matching) != 1:
            warnings.append(f"Incompatible or ambiguous comparison for {first['id']}: "
                            'definitions, basis, units, scope, fiscal period and actual duration '
                            'must match uniquely.')
        else:
            old, new = Decimal(first['value']), Decimal(second['value'])
            with localcontext() as context:
                context.prec = _precision(old, new)
                change = new - old
                result['absolute_change'] = format(change, 'f')
                if old > 0:
                    context.clear_flags()
                    percentage = change * Decimal(100) / old
                    result['percentage_change'] = format(percentage, '.2f') if percentage == percentage.quantize(Decimal('0.01')) else format(percentage, 'f')
                    if context.flags[Inexact]:
                        warnings.append(f"Percentage change for {first['id']} is rounded to "
                                        f'{context.prec} significant Decimal digits.')
                else:
                    warnings.append(f"Percentage change unavailable for {first['id']}: "
                                    'baseline value is zero or negative.')
        comparisons.append(result)
    matched_ids = {row['run_b_metric_id'] for row in comparisons}
    for second in second_metrics:
        if second['id'] not in matched_ids:
            warnings.append(f"No unique comparable baseline for {second['id']} in {run_a}.")
    return {'run_a': run_a, 'run_b': run_b, 'comparisons': comparisons,
            'warnings': list(dict.fromkeys(warnings))}
