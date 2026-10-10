"""Read as-filed insider evidence without reconstructing personal holdings or intent."""

import json
from decimal import Decimal, localcontext

from invest.models import DomainError

RESEARCH_TYPE = 'MANAGEMENT_INSIDER_ACTIVITY'
RUN_COLUMNS = ('id', 'skill_name', 'skill_version', 'schema_version', 'company_name',
               'ticker', 'security_id', 'cik', 'researched_as_of', 'imported_at',
               'coverage_status', 'summary_json')
PERSON_COLUMNS = ('person_id', 'name', 'reporting_owner_type', 'reporting_owner_cik',
                  'roles_json', 'identity_source_id')
SOURCE_COLUMNS = ('source_id', 'source_type', 'publisher', 'url', 'accession_number',
                  'filed_at', 'accepted_at', 'accessed_at', 'cik', 'is_amendment',
                  'original_accession_number', 'source_locator')
TRANSACTION_COLUMNS = ('transaction_id', 'person_id', 'source_id', 'source_row_id',
                       'transaction_date', 'table_type', 'security_title', 'transaction_code',
                       'acquired_disposed', 'quantity_text', 'price_text', 'price_currency',
                       'ownership_form', 'indirect_nature', 'purchase_venue',
                       'rule_10b5_1_status', 'review_status', 'purchase_venue_locator',
                       'supersedes_id', 'duplicate_of_id', 'notes')
OWNERSHIP_COLUMNS = ('holding_id', 'person_id', 'source_id', 'source_row_id', 'as_of_date',
                     'table_type', 'security_title', 'quantity_text', 'ownership_form',
                     'indirect_nature', 'notes')
COMPENSATION_COLUMNS = ('compensation_id', 'person_id', 'fiscal_year', 'compensation_type',
                        'value_text', 'currency', 'value_basis', 'terms', 'source_id',
                        'source_locator')
CATEGORIES = {'P': 'PURCHASE', 'S': 'SALE', 'M': 'OPTION_EXERCISE_OR_CONVERSION',
              'A': 'AWARD_OR_GRANT', 'F': 'TAX_OR_EXERCISE_PAYMENT', 'G': 'GIFT'}
GROUP_FIELDS = ('person_id', 'transaction_category', 'security_title', 'table_type',
                'acquired_disposed', 'ownership_form', 'indirect_ownership_nature')
HOLDING_FIELDS = ('person_id', 'security_title', 'table_type', 'ownership_form',
                  'indirect_ownership_nature')
BOUNDARY = ('Reported gross line values are quantity times disclosed price, not realized gain, '
            'investment return, tax basis, execution proceeds or cash compensation. Ownership '
            'records are dated as-filed observations, never calculated current holdings.')


def transaction_category(code):
    return CATEGORIES.get(code, 'OTHER')


def _select(ledger, table, columns, run_id, order):
    return [dict(zip(columns, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE run_id=? ORDER BY {order}", (run_id,))]


def _runs(ledger, ticker=None, run_id=None):
    where, parameters = '', [RESEARCH_TYPE]
    for column, value in (('ticker', ticker), ('id', run_id)):
        if value is not None:
            where += f' AND UPPER({column})=UPPER(?)' if column == 'ticker' else f' AND {column}=?'
            parameters.append(value)
    return [dict(zip(RUN_COLUMNS, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(RUN_COLUMNS)} FROM research_runs WHERE research_type=?{where} "
        'ORDER BY researched_as_of DESC, imported_at DESC, id DESC', parameters)]


def _run(ledger, run_id):
    rows = _runs(ledger, run_id=run_id)
    if not rows:
        raise DomainError('Unknown insider research run', 1)
    return rows[0]


def _metadata(run):
    return {'research_run_id': run['id'], **{key: value for key, value in run.items()
                                          if key not in {'id', 'summary_json'}}}


def list_runs(ledger, ticker=None):
    return {'runs': [{**json.loads(row['summary_json']), **_metadata(row)}
                     for row in _runs(ledger, ticker=ticker)]}


def show(ledger, run_id):
    run = _run(ledger, run_id)
    row = ledger.connection.execute(
        'SELECT package_json FROM research_runs WHERE id=? AND research_type=?',
        (run_id, RESEARCH_TYPE)).fetchone()
    return {**json.loads(row[0]), **_metadata(run)}


def _people(ledger, run_id, person=None):
    rows = _select(ledger, 'research_insider_people', PERSON_COLUMNS, run_id, 'person_id')
    for row in rows:
        row['id'] = row.pop('person_id')
        row['roles'] = json.loads(row.pop('roles_json'))
    if person is not None and person not in {row['id'] for row in rows}:
        raise DomainError('Unknown insider reporting person', 1)
    return [row for row in rows if person is None or row['id'] == person]


def _sources(ledger, run_id):
    rows = _select(ledger, 'research_sources', SOURCE_COLUMNS, run_id, 'source_id')
    for row in rows:
        row['id'] = row.pop('source_id')
        row['is_amendment'] = bool(row['is_amendment'])
    return {row['id']: row for row in rows}


def _context(run):
    saved = json.loads(run['summary_json'])
    return {'scope': saved.get('scope'), 'limitations': saved.get('limitations', []),
            'warnings': list(dict.fromkeys([*saved.get('warnings', []), BOUNDARY]))}


def _transactions(ledger, run_id):
    rows = _select(ledger, 'research_insider_transactions', TRANSACTION_COLUMNS, run_id,
                   'transaction_date, transaction_id')
    sources = _sources(ledger, run_id)
    superseded = {row['supersedes_id'] for row in rows if row['supersedes_id'] is not None}
    for row in rows:
        row['id'] = row.pop('transaction_id')
        row['quantity'] = row.pop('quantity_text')
        row['price_per_unit'] = row.pop('price_text')
        row['indirect_ownership_nature'] = row.pop('indirect_nature')
        row['transaction_category'] = transaction_category(row['transaction_code'])
        reason = ('UNRESOLVED' if row['review_status'] != 'VERIFIED' else
                  'DUPLICATE' if row['duplicate_of_id'] is not None else
                  'SUPERSEDED' if row['id'] in superseded else None)
        row['effective'] = reason is None
        row['exclusion_reason'] = reason
        row['source'] = sources[row['source_id']]
    by_id = {row['id']: row for row in rows}
    for row in rows:
        row['linked_sources'] = [by_id[row[key]]['source']
                                 for key in ('supersedes_id', 'duplicate_of_id') if row[key]]
    return rows


def activity(ledger, run_id, person=None):
    run = _run(ledger, run_id)
    people = _people(ledger, run_id, person)
    rows = [row for row in _transactions(ledger, run_id)
            if person is None or row['person_id'] == person]
    context = _context(run)
    context['warnings'].extend(f"Transaction {row['id']} excluded: {row['exclusion_reason']}."
                               for row in rows if not row['effective'])
    return {**_metadata(run), **context, 'people': people, 'transactions': rows,
            'sources': list(_sources(ledger, run_id).values())}


def ownership(ledger, run_id, person=None):
    run = _run(ledger, run_id)
    people = _people(ledger, run_id, person)
    sources = _sources(ledger, run_id)
    rows = _select(ledger, 'research_insider_ownership', OWNERSHIP_COLUMNS, run_id,
                   'as_of_date, holding_id')
    observations, latest_dates = [], {}
    for row in rows:
        if person is not None and row['person_id'] != person:
            continue
        row['id'] = row.pop('holding_id')
        row['reported_quantity'] = row.pop('quantity_text')
        row['indirect_ownership_nature'] = row.pop('indirect_nature')
        row['source'] = sources[row['source_id']]
        observations.append(row)
        key = tuple(row[field] for field in HOLDING_FIELDS)
        latest_dates[key] = max(row['as_of_date'], latest_dates.get(key, row['as_of_date']))
    latest = [row for row in observations
              if row['as_of_date'] == latest_dates[tuple(row[field] for field in HOLDING_FIELDS)]]
    return {**_metadata(run), **_context(run), 'people': people, 'observations': observations,
            'latest_observations': latest, 'sources': list(sources.values())}


def _text(value):
    result = format(value, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def _sum(values):
    if not values:
        return '0'
    numbers = [Decimal(value) for value in values]
    with localcontext() as context:
        context.prec = max(64, max(number.adjusted() for number in numbers)
                           - min(number.as_tuple().exponent for number in numbers)
                           + len(str(len(numbers))) + 4)
        return _text(sum(numbers, Decimal(0)))


def _product(quantity, price):
    first, second = Decimal(quantity), Decimal(price)
    with localcontext() as context:
        context.prec = max(64, len(first.as_tuple().digits) + len(second.as_tuple().digits) + 4)
        return _text(first * second)


def _groups(rows):
    grouped = {}
    for row in rows:
        if row['effective']:
            grouped.setdefault(tuple(row[field] for field in GROUP_FIELDS), []).append(row)
    groups = []
    for key, transactions in sorted(grouped.items(), key=lambda item: json.dumps(item[0])):
        values = {}
        if key[1] in {'PURCHASE', 'SALE'}:
            for row in transactions:
                if row['price_per_unit'] is not None:
                    values.setdefault(row['price_currency'], []).append(
                        _product(row['quantity'], row['price_per_unit']))
        groups.append({**dict(zip(GROUP_FIELDS, key, strict=True)), 'count': len(transactions),
                       'quantity': _sum([row['quantity'] for row in transactions]),
                       'gross_line_values': {currency: _sum(amounts)
                                             for currency, amounts in sorted(values.items())},
                       'unknown_price_count': sum(row['price_per_unit'] is None
                                                  for row in transactions)})
    return groups


def summary(ledger, run_id):
    run = _run(ledger, run_id)
    people = _people(ledger, run_id)
    sources = _sources(ledger, run_id)
    compensation = _select(ledger, 'research_insider_compensation', COMPENSATION_COLUMNS,
                           run_id, 'person_id, fiscal_year, compensation_id')
    grouped = {}
    for row in compensation:
        row['id'] = row.pop('compensation_id')
        row['value'] = row.pop('value_text')
        row['source'] = sources[row['source_id']]
        grouped.setdefault((row['person_id'], row['fiscal_year']), []).append(row)
    arrangements = [{'person_id': person_id, 'fiscal_year': year, 'items': rows,
                     'reported_totals': [row for row in rows
                                         if row['compensation_type'] == 'SUMMARY_COMPENSATION_TOTAL']}
                    for (person_id, year), rows in grouped.items()]
    rows = _transactions(ledger, run_id)
    context = _context(run)
    context['warnings'].extend(f"Transaction {row['id']} excluded: {row['exclusion_reason']}."
                               for row in rows if not row['effective'])
    context['warnings'].extend(f"Transaction {row['id']} has no disclosed price."
                               for row in rows if row['effective'] and
                               row['transaction_category'] in {'PURCHASE', 'SALE'} and
                               row['price_per_unit'] is None)
    return {**_metadata(run), **context, 'people': people, 'compensation': arrangements,
            'transaction_groups': _groups(rows),
            'transaction_counts': {category: sum(row['effective'] and
                                                 row['transaction_category'] == category
                                                 for row in rows)
                                   for category in (*CATEGORIES.values(), 'OTHER')},
            'sources': list(sources.values())}
