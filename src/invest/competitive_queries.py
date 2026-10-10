"""Read immutable peer evidence and compare strictly compatible reported observations."""

import json
from decimal import Decimal, Inexact, localcontext

from invest.models import DomainError

RESEARCH_TYPE = 'COMPETITIVE_POSITION_PEER_COMPARISON'
RUN_COLUMNS = ('id', 'skill_name', 'skill_version', 'schema_version', 'company_name',
               'ticker', 'security_id', 'cik', 'researched_as_of', 'imported_at',
               'coverage_status', 'summary_json')
ENTITY_COLUMNS = ('entity_id', 'role', 'name', 'ticker', 'cik', 'security_id',
                  'relationship', 'rationale', 'selection_source_id')
OVERLAP_COLUMNS = ('overlap_id', 'peer_id', 'market', 'geography', 'subject_segment',
                   'peer_segment', 'overlap_type', 'description', 'uncertainty',
                   'subject_source_id', 'peer_source_id')
FINDING_COLUMNS = ('finding_id', 'peer_id', 'overlap_id', 'kind', 'factual_basis',
                   'interpretation', 'assumptions', 'uncertainty', 'source_id',
                   'source_locator', 'corroborating_source_ids_json')
METRIC_COLUMNS = ('metric_id', 'entity_id', 'metric_code', 'metric_definition', 'value_text',
                  'unit', 'accounting_basis', 'period_type', 'period_start', 'period_end',
                  'scope', 'segment_name', 'overlap_id', 'source_id', 'source_locator')
KEYS = ('metric_code', 'metric_definition', 'accounting_basis', 'unit', 'period_type',
        'period_start', 'period_end', 'scope', 'overlap_id')
BOUNDARY = ('Descriptive operating-company evidence only; business competition does not '
            'establish investment suitability. Consolidated measures do not establish '
            'strength in an overlapping market.')


def _select(ledger, table, columns, run_id, order):
    return [dict(zip(columns, values, strict=True)) for values in ledger.connection.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE run_id=? ORDER BY {order}",
        (run_id,))]


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
        raise DomainError('Unknown competitive research run', 1)
    return rows[0]


def _metadata(row):
    return {'research_run_id': row['id'], **{key: value for key, value in row.items()
                                           if key not in {'id', 'summary_json'}}}


def list_runs(ledger, ticker=None):
    return {'runs': [{**json.loads(row['summary_json']), **_metadata(row)}
                     for row in _runs(ledger, ticker=ticker)]}


def show(ledger, run_id):
    row = _run(ledger, run_id)
    package = ledger.connection.execute(
        'SELECT package_json FROM research_runs WHERE id=? AND research_type=?',
        (run_id, RESEARCH_TYPE)).fetchone()
    return {**json.loads(package[0]), **_metadata(row)}


def _entities(ledger, run_id):
    return _select(ledger, 'research_competitive_entities', ENTITY_COLUMNS, run_id, 'entity_id')


def _overlaps(ledger, run_id):
    return _select(ledger, 'research_competitive_overlaps', OVERLAP_COLUMNS, run_id, 'overlap_id')


def _metrics(ledger, run_id):
    rows = _select(ledger, 'research_competitive_metrics', METRIC_COLUMNS, run_id, 'metric_id')
    for row in rows:
        row['id'] = row.pop('metric_id')
        row['value'] = row.pop('value_text')
    return rows


def summary(ledger, run_id):
    run = _run(ledger, run_id)
    saved = json.loads(run['summary_json'])
    entities, overlaps, metrics = _entities(ledger, run_id), _overlaps(ledger, run_id), _metrics(ledger, run_id)
    findings = _select(ledger, 'research_competitive_findings', FINDING_COLUMNS, run_id, 'finding_id')
    for finding in findings:
        finding['corroborating_source_ids'] = json.loads(finding.pop('corroborating_source_ids_json'))
    peers = []
    for entity in entities:
        if entity['role'] == 'PEER':
            peers.append({**entity, 'overlaps': [row for row in overlaps if row['peer_id'] == entity['entity_id']],
                          'findings': [row for row in findings if row['peer_id'] == entity['entity_id']],
                          'metrics': [row for row in metrics if row['entity_id'] == entity['entity_id']]})
    sources = _select(ledger, 'research_sources',
                      ('source_id', 'source_type', 'publisher', 'url', 'published_at',
                       'accessed_at', 'source_locator'), run_id, 'source_id')
    subject = next((entity for entity in entities if entity['role'] == 'SUBJECT'), None)
    return {**_metadata(run), 'subject': subject, 'peers': peers,
            'subject_metrics': [row for row in metrics if row['entity_id'] == 'subject'],
            'sources': sources, 'scope': saved.get('scope'),
            'limitations': saved.get('limitations', []),
            'warnings': list(dict.fromkeys([*saved.get('warnings', []), BOUNDARY]))}


def _key(metric):
    return tuple(' '.join(metric[key].split()) if key == 'metric_definition' else metric[key]
                 for key in KEYS)


def _segment_matches(metric, peer_id, overlaps):
    if metric['scope'] == 'CONSOLIDATED':
        return metric['segment_name'] is None and metric['overlap_id'] is None
    overlap = overlaps.get(metric['overlap_id'])
    if not overlap or overlap['peer_id'] != peer_id:
        return False
    expected = overlap['subject_segment' if metric['entity_id'] == 'subject' else 'peer_segment']
    return ' '.join(metric['segment_name'].split()) == ' '.join(expected.split())


def _precision(first, second):
    exponent = min(first.as_tuple().exponent, second.as_tuple().exponent)
    integer_digits = max(first.adjusted(), second.adjusted()) + 1
    return max(64, integer_digits - exponent + 4,
               len(first.as_tuple().digits) + len(second.as_tuple().digits) + 16)


def _comparison(peer_id, key, subjects, peers, overlaps):
    first, second = subjects[0] if len(subjects) == 1 else None, peers[0] if len(peers) == 1 else None
    row = {'peer_id': peer_id, **dict(zip(KEYS, key, strict=True)),
           'subject_value': first['value'] if first else None,
           'peer_value': second['value'] if second else None,
           'subject_observations': subjects, 'peer_observations': peers,
           'comparison_status': 'NOT_COMPARABLE', 'absolute_difference': None,
           'percentage_difference': None, 'warnings': []}
    for prefix, metric in (('subject', first), ('peer', second)):
        for output, field in (('metric_id', 'id'), ('source_id', 'source_id'),
                              ('source_locator', 'source_locator'), ('segment_name', 'segment_name')):
            row[f'{prefix}_{output}'] = metric[field] if metric else None
    if first is None or second is None:
        row['warnings'].append('Missing or ambiguous reported observations; definitions, basis, '
                               'units, exact dates, scope and overlap must match uniquely.')
    elif not all(_segment_matches(metric, peer_id, overlaps) for metric in (first, second)):
        row['warnings'].append('Segment comparison requires corresponding segments of the same '
                               'explicit market overlap.')
    else:
        row['comparison_status'] = 'COMPARABLE'
        subject, peer = Decimal(first['value']), Decimal(second['value'])
        with localcontext() as context:
            context.prec = _precision(subject, peer)
            difference = subject - peer
            row['absolute_difference'] = format(difference, 'f')
            if peer > 0:
                context.clear_flags()
                percentage = difference * Decimal(100) / peer
                rounded = context.flags[Inexact]
                row['percentage_difference'] = format(percentage, 'f')
                if rounded:
                    row['warnings'].append('Percentage difference rounded to '
                                           f'{context.prec} significant Decimal digits.')
            else:
                row['warnings'].append('Percentage difference unavailable: peer value is zero '
                                       'or negative.')
    return row


def matrix(ledger, run_id, peer=None):
    run = _run(ledger, run_id)
    entities = [row for row in _entities(ledger, run_id) if row['role'] == 'PEER']
    if peer is not None:
        entities = [row for row in entities if row['entity_id'] == peer]
        if not entities:
            raise DomainError('Unknown competitive peer', 1)
    metrics = _metrics(ledger, run_id)
    overlaps = {row['overlap_id']: row for row in _overlaps(ledger, run_id)}
    rows = []
    for entity in entities:
        peer_id = entity['entity_id']
        grouped = {}
        for metric in metrics:
            if metric['entity_id'] in {'subject', peer_id}:
                sides = grouped.setdefault(_key(metric), {'subject': [], peer_id: []})
                sides[metric['entity_id']].append(metric)
        for key, sides in sorted(grouped.items(), key=lambda item: json.dumps(item[0])):
            rows.append(_comparison(peer_id, key, sides['subject'], sides[peer_id], overlaps))
    saved = json.loads(run['summary_json'])
    warnings = [*saved.get('warnings', []), BOUNDARY]
    warnings.extend(warning for row in rows for warning in row['warnings'])
    return {**_metadata(run), 'rows': rows, 'limitations': saved.get('limitations', []),
            'warnings': list(dict.fromkeys(warnings))}
