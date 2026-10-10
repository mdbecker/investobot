"""Read immutable news evidence and conservatively compare stable identities."""

import json
from datetime import date

from invest.models import DomainError
from invest.research_identity import same_research_company

RESEARCH_TYPE = 'NEWS_CATALYSTS_THESIS_CHANGES'
RUN_COLUMNS = ('id', 'skill_name', 'skill_version', 'schema_version', 'company_name',
               'ticker', 'security_id', 'cik', 'researched_as_of', 'imported_at',
               'coverage_status', 'summary_json')
DELTA_KEYS = ('new_events', 'updated_events', 'new_evidence_only', 'catalyst_changes',
              'thesis_changes', 'follow_up_changes', 'not_reobserved')


def _text(value):
    return ' '.join(value.split()) if isinstance(value, str) else value


def _normalized(value):
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_normalized(item) for item in value),
                      key=lambda item: json.dumps(item, sort_keys=True))
    return _text(value)


def _select(ledger, table, columns, run_id):
    return [dict(zip(columns, row, strict=True)) for row in ledger.connection.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE run_id=?", (run_id,))]


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
        raise DomainError('Unknown news research run', 1)
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


def _scope(ledger, run_id):
    columns = ('window_start', 'window_end', 'coverage_status',
               'searched_source_types_json', 'coverage_notes')
    rows = _select(ledger, 'research_news_scopes', columns, run_id)
    if not rows:
        raise DomainError('News research scope is missing', 3)
    result = rows[0]
    result['searched_source_types'] = json.loads(result.pop('searched_source_types_json'))
    return result


def _sources(ledger, run_id):
    return _select(ledger, 'research_sources',
                   ('run_id', 'source_id', 'source_type', 'publisher', 'url', 'published_at',
                    'accessed_at', 'source_locator'), run_id)


def _events(ledger, run_id):
    columns = ('event_key', 'title', 'category', 'event_date', 'date_status', 'event_status',
               'affected_segments_json', 'primary_source_id', 'source_ids_json',
               'implications_json', 'follow_up_questions_json',
               'status_source_id', 'status_source_locator')
    facts = _select(ledger, 'research_news_facts',
                    ('event_key', 'fact_key', 'statement', 'verification_status',
                     'source_id', 'source_locator'), run_id)
    result = []
    for event in _select(ledger, 'research_news_events', columns, run_id):
        for key in ('affected_segments', 'source_ids', 'implications', 'follow_up_questions'):
            event[key] = json.loads(event.pop(key + '_json'))
        own_facts = sorted((fact for fact in facts if fact['event_key'] == event['event_key']),
                           key=lambda fact: fact['fact_key'])
        event['verified_facts'] = [fact for fact in own_facts
                                   if fact['verification_status'] == 'VERIFIED']
        event['disputed_facts'] = [fact for fact in own_facts
                                  if fact['verification_status'] == 'DISPUTED']
        result.append(event)
    return sorted(result, key=lambda event: (event['event_date'] or '', event['event_key']))


def _catalysts(ledger, run_id):
    rows = _select(ledger, 'research_news_catalysts',
                   ('catalyst_id', 'title', 'related_event_key', 'scheduled_date',
                    'date_status', 'status', 'source_id', 'source_locator', 'qualifiers'), run_id)
    return sorted(rows, key=lambda row: row['catalyst_id'])


def _theses(ledger, run_id):
    rows = _select(ledger, 'research_news_theses',
                   ('thesis_id', 'statement', 'assessment', 'rationale', 'uncertainty',
                    'related_event_keys_json'), run_id)
    for row in rows:
        row['related_event_keys'] = json.loads(row.pop('related_event_keys_json'))
    return sorted(rows, key=lambda row: row['thesis_id'])


def summary(ledger, run_id):
    run = _run(ledger, run_id)
    events = _events(ledger, run_id)
    warnings = list(json.loads(run['summary_json']).get('warnings', []))
    scope = _scope(ledger, run_id)
    if scope['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('Incomplete declared coverage; absence is not evidence of no news.')
    for event in events:
        if event['disputed_facts']:
            warnings.append(f"Disputed claims remain unresolved for {event['event_key']}.")
    return {**_metadata(run), 'company': run['company_name'], 'scope': scope,
            'events': events, 'catalysts': _catalysts(ledger, run_id),
            'theses': _theses(ledger, run_id), 'sources': _sources(ledger, run_id),
            'open_follow_up_questions': [dict(question, event_key=event['event_key'])
                                         for event in events
                                         for question in event['follow_up_questions']
                                         if question['status'] == 'OPEN'],
            'warnings': sorted(set(warnings))}


def context(ledger, ticker):
    runs = _runs(ledger, ticker=ticker)
    if not runs:
        return {'baseline_available': False, 'ticker': ticker, 'events': [],
                'catalysts': [], 'theses': [], 'open_follow_up_questions': []}
    run = runs[0]
    events = _select(ledger, 'research_news_events',
                     ('event_key', 'title', 'event_status', 'event_date',
                      'source_ids_json', 'follow_up_questions_json'), run['id'])
    questions = []
    for event in events:
        event['source_ids'] = json.loads(event.pop('source_ids_json'))
        questions.extend(dict(question, event_key=event['event_key'])
                         for question in json.loads(event.pop('follow_up_questions_json'))
                         if question['status'] == 'OPEN')
    return {**_metadata(run), 'baseline_available': True,
            'scope': _scope(ledger, run['id']),
            'events': sorted((event for event in events
                              if event['event_status'] not in {'RESOLVED', 'RETRACTED'}),
                             key=lambda event: event['event_key']),
            'catalysts': [item for item in _catalysts(ledger, run['id'])
                          if item['status'] not in {'OCCURRED', 'CANCELLED'}],
            'theses': _theses(ledger, run['id']), 'open_follow_up_questions': questions,
            'warnings': json.loads(run['summary_json']).get('warnings', [])}


def _links(snapshot, ids):
    return [source for source in snapshot['sources'] if source['source_id'] in set(ids)]


def _event_links(snapshot, event):
    ids = set(event['source_ids'])
    ids.update(fact['source_id'] for fact in event['verified_facts'] + event['disputed_facts'])
    return _links(snapshot, ids)


def _fact_map(event):
    return {fact['fact_key']: fact for fact in event['verified_facts']}


def _question_changes(before, after, old, new):
    first = {question['id']: question for question in before['follow_up_questions']}
    second = {question['id']: question for question in after['follow_up_questions']}
    result = []
    for key in sorted(set(first) | set(second)):
        a, b = first.get(key), second.get(key)
        fields = ('status', 'answered_fact_key', 'closure_limitation', 'evidence_needed')
        if a and b and all(_normalized(a.get(field)) == _normalized(b.get(field))
                           for field in fields):
            continue
        result.append({'event_key': after['event_key'], 'question_id': key,
                       'old_status': a['status'] if a else None,
                       'new_status': b['status'] if b else 'NOT_REOBSERVED',
                       'before': a, 'after': b, 'from_run_id': old['research_run_id'],
                       'to_run_id': new['research_run_id'],
                       'sources': _event_links(new, after)})
    return result


def _compare_events(old, new, result):
    first = {event['event_key']: event for event in old['events']}
    second = {event['event_key']: event for event in new['events']}
    for key in sorted(set(first) | set(second)):
        a, b = first.get(key), second.get(key)
        if b is None:
            result['not_reobserved'].append({'kind': 'EVENT', 'event_key': key,
                                             'status': 'NOT_REOBSERVED', 'before': a,
                                             'after': None, 'sources': _event_links(old, a)})
            continue
        links = _event_links(new, b)
        if a is None:
            observation = 'NEWLY_OBSERVED'
            if b['event_date'] and b['event_date'] < new['scope']['window_start']:
                observation = 'PREVIOUSLY_OCCURRING_NEWLY_OBSERVED'
            result['new_events'].append({'event_key': key, 'observation_status': observation,
                                         'before': None, 'after': b, 'sources': links})
            similar = [event for event in first.values()
                       if _text(event['title']).casefold() == _text(b['title']).casefold()]
            if similar:
                result['warnings'].append(f'Possible ambiguous duplicate title for {key}; '
                                          'different stable keys remain distinct.')
            continue
        facts_a, facts_b = _fact_map(a), _fact_map(b)
        added = [facts_b[key] for key in sorted(set(facts_b) - set(facts_a))]
        removed = [facts_a[key] for key in sorted(set(facts_a) - set(facts_b))]
        revised = [{'before': facts_a[key], 'after': facts_b[key]}
                   for key in sorted(set(facts_a) & set(facts_b))
                   if _text(facts_a[key]['statement']) != _text(facts_b[key]['statement'])]
        changes = []
        if added:
            changes.append('FACT_ADDED')
        if revised or removed:
            changes.append('FACT_REVISED')
        fields = ((('event_status',), 'STATUS_CHANGED'),
                  (('event_date', 'date_status'), 'DATE_CHANGED'),
                  (('affected_segments',), 'SEGMENT_CHANGED'),
                  (('implications',), 'IMPLICATION_CHANGED'))
        for keys, kind in fields:
            if any(_normalized(a[field]) != _normalized(b[field]) for field in keys):
                changes.append(kind)
        if changes:
            result['updated_events'].append({'event_key': key, 'change_types': changes,
                                             'added_facts': added, 'revised_facts': revised,
                                             'removed_facts': removed, 'before': a, 'after': b,
                                             'sources': links,
                                             'before_sources': _event_links(old, a),
                                             'after_sources': links})
        else:
            old_sources = _event_links(old, a)
            old_evidence = {source['url'] for source in old_sources}
            added_sources = [source for source in links
                             if source['url'] not in old_evidence]
            old_urls = {source['source_id']: source['url'] for source in old_sources}
            new_urls = {source['source_id']: source['url'] for source in links}
            old_refs = {(fact['fact_key'], old_urls[fact['source_id']], _text(fact['source_locator']))
                        for fact in a['verified_facts']}
            new_refs = {(fact['fact_key'], new_urls[fact['source_id']], _text(fact['source_locator']))
                        for fact in b['verified_facts']}
            if added_sources or new_refs - old_refs:
                result['new_evidence_only'].append({'event_key': key,
                                                    'added_source_ids': sorted(
                                                        source['source_id'] for source in added_sources),
                                                    'before': a, 'after': b,
                                                    'before_sources': old_sources,
                                                    'after_sources': links,
                                                    'sources': added_sources or links})
        result['follow_up_changes'].extend(_question_changes(a, b, old, new))


def _compare_records(old, new, result, kind):
    collection, id_field = ('catalysts', 'catalyst_id') if kind == 'CATALYST' else ('theses', 'thesis_id')
    first = {item[id_field]: item for item in old[collection]}
    second = {item[id_field]: item for item in new[collection]}
    for key in sorted(set(first) | set(second)):
        a, b = first.get(key), second.get(key)
        if b is None:
            ids = [a['source_id']] if kind == 'CATALYST' else {
                source for event in old['events']
                if event['event_key'] in a['related_event_keys'] for source in event['source_ids']}
            result['not_reobserved'].append({'kind': kind, id_field: key,
                                             'status': 'NOT_REOBSERVED', 'before': a, 'after': None,
                                             'sources': _links(old, ids)})
            continue
        if kind == 'CATALYST':
            fields = ('status', 'scheduled_date', 'date_status', 'qualifiers')
            if a and all(_normalized(a[field]) == _normalized(b[field]) for field in fields):
                continue
            result['catalyst_changes'].append({id_field: key, 'before': a, 'after': b,
                                               'old_status': a['status'] if a else None,
                                               'new_status': b['status'],
                                               'old_date': a['scheduled_date'] if a else None,
                                               'new_date': b['scheduled_date'],
                                               'source_ids': [b['source_id']],
                                               'before_sources': _links(old, [a['source_id']]) if a else [],
                                               'after_sources': _links(new, [b['source_id']]),
                                               'sources': _links(new, [b['source_id']])})
        else:
            incompatible = a and _text(a['statement']) != _text(b['statement'])
            if a and not incompatible and all(_normalized(a[field]) == _normalized(b[field])
                                               for field in ('assessment', 'rationale', 'uncertainty',
                                                             'related_event_keys')):
                continue
            ids = {source for event in new['events']
                   if event['event_key'] in b['related_event_keys'] for source in event['source_ids']}
            old_ids = {source for event in old['events']
                       if a and event['event_key'] in a['related_event_keys']
                       for source in event['source_ids']}
            status = 'INCOMPATIBLE' if incompatible else ('NEWLY_TRACKED' if a is None else 'REASSESSED')
            result['thesis_changes'].append({id_field: key, 'status': status, 'before': a,
                                             'after': b, 'statement': b['statement'],
                                             'old_assessment': a['assessment'] if a else None,
                                             'new_assessment': b['assessment'],
                                             'related_event_keys': b['related_event_keys'],
                                             'source_ids': sorted(ids), 'sources': _links(new, ids),
                                             'before_sources': _links(old, old_ids),
                                             'after_sources': _links(new, ids),
                                             'uncertainty': b['uncertainty']})
            if incompatible:
                result['warnings'].append(f'Incompatible hypothesis statement under thesis ID {key}.')


def compare(ledger, run_old, run_new):
    first, second = _run(ledger, run_old), _run(ledger, run_new)
    if not same_research_company(first, second):
        raise DomainError('Incompatible news company identities', 3)
    old, new = summary(ledger, run_old), summary(ledger, run_new)
    comparable = all(snapshot['scope']['coverage_status'] == 'COMPLETE_WITHIN_DECLARED_SCOPE'
                     for snapshot in (old, new))
    comparable = comparable and old['scope']['searched_source_types'] == new['scope']['searched_source_types']
    windows_overlap = (old['scope']['window_start'] <= new['scope']['window_end'] and
                       new['scope']['window_start'] <= old['scope']['window_end'])
    result = {'company': second['company_name'], 'from_run_id': run_old, 'to_run_id': run_new,
              'from_scope': old['scope'], 'to_scope': new['scope'],
              'coverage_comparable': comparable and windows_overlap,
              **{key: [] for key in DELTA_KEYS},
              'warnings': old['warnings'] + new['warnings']}
    if not windows_overlap:
        gap = (date.fromisoformat(new['scope']['window_start']) -
               date.fromisoformat(old['scope']['window_end'])).days
        result['warnings'].append('Monitoring windows do not overlap; absence cannot imply resolution.')
        if gap > 1:
            result['warnings'].append('A gap exists between the declared monitoring windows.')
    if not result['coverage_comparable']:
        result['warnings'].append('Coverage is not fully comparable; missing stories remain unobserved.')
    if first['researched_as_of'] > second['researched_as_of']:
        result['warnings'].append('Selected newer run has an earlier research date; explicit order is preserved.')
    _compare_events(old, new, result)
    _compare_records(old, new, result, 'CATALYST')
    _compare_records(old, new, result, 'THESIS')
    for key in DELTA_KEYS:
        for item in result[key]:
            item.setdefault('from_run_id', run_old)
            item.setdefault('to_run_id', run_new)
    result['warnings'] = sorted(set(result['warnings']))
    result['counts'] = {key: len(result[key]) for key in DELTA_KEYS}
    result['counts']['warnings'] = len(result['warnings'])
    return result


def changes(ledger, ticker):
    runs = _runs(ledger, ticker=ticker)
    if runs:
        newest = runs[0]
        compatible = [run for run in runs[1:] if same_research_company(run, newest)]
        if compatible:
            return {'baseline_available': True, **compare(ledger, compatible[0]['id'], newest['id'])}
    return {'baseline_available': False, 'ticker': ticker,
            'to_run_id': runs[0]['id'] if runs else None,
            **{key: [] for key in DELTA_KEYS}, 'counts': dict(dict.fromkeys(DELTA_KEYS, 0), warnings=1),
            'warnings': ['Fewer than two compatible accepted runs; no comparison baseline.']}
