"""Read immutable fund evidence and compute only observed, dated concentration."""

import json
from decimal import Decimal, localcontext

from invest.models import DomainError

RESEARCH_TYPE = 'ETF_MUTUAL_FUND_DILIGENCE'
RUN_COLUMNS = ('id', 'skill_name', 'skill_version', 'schema_version', 'company_name',
               'ticker', 'security_id', 'cik', 'researched_as_of', 'imported_at',
               'coverage_status', 'summary_json')
PROFILE_COLUMNS = ('registrant_cik', 'series_id', 'class_id', 'fund_type', 'strategy_type',
                   'share_class_name', 'adviser', 'isin', 'exchange', 'methodology_json', 'snapshot_json')
SOURCE_COLUMNS = ('source_id', 'source_type', 'publisher', 'url', 'published_at',
                  'filed_at', 'accessed_at', 'source_locator', 'accession_number', 'cik')
METRIC_COLUMNS = ('metric_id', 'code', 'value_text', 'unit', 'scope', 'period_start',
                  'period_end', 'observed_as_of', 'waiver_end_date', 'source_id',
                  'source_locator', 'notes')
HOLDING_COLUMNS = ('holding_id', 'name', 'security_identifier', 'asset_class',
                   'weight_pct_text', 'source_id', 'source_locator')
FINDING_COLUMNS = ('finding_id', 'category', 'fact', 'interpretation', 'uncertainty',
                   'source_ids_json', 'source_locator')
FEES = {'GROSS_EXPENSE_RATIO', 'NET_EXPENSE_RATIO', 'DISTRIBUTION_12B1_FEE',
        'MAX_FRONT_LOAD', 'MAX_DEFERRED_LOAD', 'REDEMPTION_FEE'}
LIQUIDITY = {'MEDIAN_BID_ASK_SPREAD', 'AVG_PREMIUM_DISCOUNT', 'AVG_DAILY_DOLLAR_VOLUME'}
DISTRIBUTIONS = {'SHORT_TERM_CAPITAL_GAIN_DISTRIBUTION', 'LONG_TERM_CAPITAL_GAIN_DISTRIBUTION',
                 'ORDINARY_INCOME_DISTRIBUTION', 'RETURN_OF_CAPITAL_DISTRIBUTION'}
BOUNDARY = ('Descriptive source-backed fund evidence; no investment suitability, replacement, '
            'wash-sale safety, investor tax liability or predicted return is established.')


def _select(ledger, table, columns, run_id, order):
    return [dict(zip(columns, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE run_id=? ORDER BY {order}", (run_id,))]


def _runs(ledger, ticker=None, run_id=None):
    where, parameters = '', [RESEARCH_TYPE]
    if ticker is not None:
        where += ' AND UPPER(ticker)=UPPER(?)'
        parameters.append(ticker)
    if run_id is not None:
        where += ' AND id=?'
        parameters.append(run_id)
    return [dict(zip(RUN_COLUMNS, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(RUN_COLUMNS)} FROM research_runs WHERE research_type=?{where} "
        'ORDER BY researched_as_of DESC, imported_at DESC, id DESC', parameters)]


def _run(ledger, run_id):
    rows = _runs(ledger, run_id=run_id)
    if not rows:
        raise DomainError('Unknown fund diligence research run', 1)
    return rows[0]


def _metadata(row):
    return {'research_run_id': row['id'], **{key: value for key, value in row.items()
                                           if key not in {'id', 'summary_json'}}}


def list_runs(ledger, ticker=None):
    """Compact accepted metadata; never retrieve immutable packages."""
    return {'runs': [{**json.loads(row['summary_json']), **_metadata(row)}
                     for row in _runs(ledger, ticker=ticker)]}


def show(ledger, run_id):
    run = _run(ledger, run_id)
    row = ledger.connection.execute(
        'SELECT package_json FROM research_runs WHERE id=? AND research_type=?',
        (run_id, RESEARCH_TYPE)).fetchone()
    return {**json.loads(row[0]), **_metadata(run)}


def _profile(ledger, run_id):
    rows = _select(ledger, 'research_fund_profiles', PROFILE_COLUMNS, run_id, 'run_id')
    if not rows:
        raise DomainError('Fund diligence profile is missing', 3)
    profile = rows[0]
    methodology = json.loads(profile.pop('methodology_json'))
    snapshot = json.loads(profile.pop('snapshot_json'))
    profile['class_name'] = profile.pop('share_class_name')
    return profile, methodology, snapshot


def _sources(ledger, run_id):
    rows = _select(ledger, 'research_sources', SOURCE_COLUMNS, run_id, 'source_id')
    for row in rows:
        row['id'] = row.pop('source_id')
        row['registrant_cik'] = row.pop('cik')
    return rows


def _metrics(ledger, run_id):
    rows = _select(ledger, 'research_fund_metrics', METRIC_COLUMNS, run_id, 'metric_id')
    for row in rows:
        row['id'] = row.pop('metric_id')
        row['value'] = row.pop('value_text')
    return rows


def _findings(ledger, run_id):
    rows = _select(ledger, 'research_fund_findings', FINDING_COLUMNS, run_id, 'finding_id')
    for row in rows:
        row['id'] = row.pop('finding_id')
        row['source_ids'] = json.loads(row.pop('source_ids_json'))
    return rows


def summary(ledger, run_id):
    """Report disclosed observations separately, with original dates and citations."""
    run = _run(ledger, run_id)
    saved = json.loads(run['summary_json'])
    profile, methodology, snapshot = _profile(ledger, run_id)
    metrics = _metrics(ledger, run_id)
    findings = _findings(ledger, run_id)
    distributions = [row for row in metrics if row['code'] in DISTRIBUTIONS]
    warnings = [*saved.get('warnings', []), BOUNDARY]
    if not distributions:
        warnings.append('Distribution history unavailable; absence does not establish tax efficiency.')
    return {**_metadata(run), 'fund': {**saved.get('fund', {}), **profile},
            'scope': saved.get('scope'), 'methodology': methodology,
            'holdings_snapshot': snapshot, 'metrics': metrics,
            'fees': [row for row in metrics if row['code'] in FEES],
            'turnover': [row for row in metrics if row['code'] == 'PORTFOLIO_TURNOVER'],
            'liquidity': [row for row in metrics if row['code'] in LIQUIDITY],
            'liquidity_findings': [row for row in findings if row['category'] == 'LIQUIDITY'],
            'distributions': distributions, 'findings': findings,
            'sources': _sources(ledger, run_id), 'limitations': saved.get('limitations', []),
            'warnings': list(dict.fromkeys(warnings))}


def _plain(value):
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def holdings(ledger, run_id):
    """Sum original disclosed weights without imputing missing allocation."""
    run = _run(ledger, run_id)
    saved = json.loads(run['summary_json'])
    profile, _, snapshot = _profile(ledger, run_id)
    rows = _select(ledger, 'research_fund_holdings', HOLDING_COLUMNS, run_id, 'holding_id')
    for row in rows:
        row['id'] = row.pop('holding_id')
        row['weight_pct'] = row.pop('weight_pct_text')
    rows.sort(key=lambda row: row['id'])
    rows.sort(key=lambda row: Decimal(row['weight_pct']), reverse=True)
    weights = [Decimal(row['weight_pct']) for row in rows]
    # At most 100 bounded weights, with potentially very long fractional precision.
    precision = max([64, *(len(value.as_tuple().digits) + abs(value.as_tuple().exponent) + 8
                            for value in weights)])
    with localcontext() as context:
        context.prec = precision
        observed = sum(weights, Decimal('0'))
        largest = sum(weights[:10], Decimal('0')) if len(weights) >= 10 else None
        residual = Decimal('100') - observed if snapshot['coverage'] == 'FULL' and observed <= 100 else None
    warnings = [*saved.get('warnings', []), BOUNDARY]
    if snapshot['coverage'] != 'FULL':
        warnings.append('Observed holdings may be incomplete; weights have not been rescaled.')
    if largest is None:
        warnings.append('Fewer than ten reported positions; largest-ten concentration unavailable.')
    if snapshot['coverage'] == 'FULL' and observed > 100:
        warnings.append('Reported full weights exceed 100% within rounding tolerance; residual unavailable.')
    label = ('Full-portfolio largest ten reported holdings' if snapshot['coverage'] == 'FULL'
             else 'Verified top-list largest ten observed holdings' if snapshot['coverage'] == 'TOP_N'
             else 'Largest ten observed holdings, potentially incomplete')
    return {**_metadata(run), 'fund': {**saved.get('fund', {}), **profile},
            'holdings_snapshot': snapshot, 'as_of_date': snapshot['as_of_date'],
            'coverage': snapshot['coverage'], 'holdings': rows,
            'observed_weight_sum_pct': _plain(observed),
            'largest_10_observed_weight_pct': _plain(largest) if largest is not None else None,
            'largest_10_observed_label': label,
            'unreported_residual_pct': _plain(residual) if residual is not None else None,
            'sources': _sources(ledger, run_id), 'limitations': saved.get('limitations', []),
            'warnings': list(dict.fromkeys(warnings))}
