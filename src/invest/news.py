"""Immutable, explicitly accepted news observations, isolated from financial state."""

import hashlib
import json
from datetime import datetime, timezone

from invest.models import DomainError
from invest.research_identity import same_research_company, verify_company
from invest.research_skills import SKILL_VERSION, SUPPORTED_SKILLS
from invest.research_storage import insert_record

DDL = [
    """CREATE TABLE research_news_scopes (
        run_id TEXT PRIMARY KEY, window_start TEXT NOT NULL, window_end TEXT NOT NULL,
        coverage_status TEXT NOT NULL CHECK(coverage_status IN
        ('COMPLETE_WITHIN_DECLARED_SCOPE','PARTIAL','BLOCKED')),
        searched_source_types_json TEXT NOT NULL, coverage_notes TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES research_runs(id))""",
    """CREATE TABLE research_news_events (
        run_id TEXT NOT NULL, event_key TEXT NOT NULL, title TEXT NOT NULL,
        category TEXT NOT NULL, event_date TEXT, date_status TEXT NOT NULL,
        event_status TEXT NOT NULL, affected_segments_json TEXT NOT NULL,
        primary_source_id TEXT NOT NULL, source_ids_json TEXT NOT NULL,
        implications_json TEXT NOT NULL, follow_up_questions_json TEXT NOT NULL,
        material_fingerprint TEXT NOT NULL, status_source_id TEXT, status_source_locator TEXT,
        PRIMARY KEY(run_id,event_key), FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,primary_source_id) REFERENCES research_sources(run_id,source_id),
        FOREIGN KEY(run_id,status_source_id) REFERENCES research_sources(run_id,source_id))""",
    "CREATE INDEX research_news_event_key_idx ON research_news_events(event_key,run_id)",
    """CREATE TABLE research_news_facts (
        run_id TEXT NOT NULL, event_key TEXT NOT NULL, fact_key TEXT NOT NULL,
        statement TEXT NOT NULL, verification_status TEXT NOT NULL
        CHECK(verification_status IN ('VERIFIED','DISPUTED')),
        source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        PRIMARY KEY(run_id,event_key,fact_key),
        FOREIGN KEY(run_id,event_key) REFERENCES research_news_events(run_id,event_key),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_news_catalysts (
        run_id TEXT NOT NULL, catalyst_id TEXT NOT NULL, title TEXT NOT NULL,
        related_event_key TEXT, scheduled_date TEXT, date_status TEXT NOT NULL,
        status TEXT NOT NULL, source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        qualifiers TEXT NOT NULL, PRIMARY KEY(run_id,catalyst_id),
        FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,related_event_key) REFERENCES research_news_events(run_id,event_key),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_news_theses (
        run_id TEXT NOT NULL, thesis_id TEXT NOT NULL, statement TEXT NOT NULL,
        assessment TEXT NOT NULL CHECK(assessment IN
        ('SUPPORTED','CHALLENGED','MIXED','INSUFFICIENT_EVIDENCE')),
        rationale TEXT NOT NULL, uncertainty TEXT NOT NULL, related_event_keys_json TEXT NOT NULL,
        PRIMARY KEY(run_id,thesis_id), FOREIGN KEY(run_id) REFERENCES research_runs(id))""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def normalized_text(value):
    return ' '.join(value.split())


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def material_fingerprint(event):
    """Titles, citations and question wording are not business developments."""
    material = {key: event[key] for key in ('category', 'event_date', 'date_status', 'event_status')}
    material['affected_segments'] = sorted(normalized_text(s) for s in event['affected_segments'])
    material['facts'] = sorted(
        [(f['fact_key'], normalized_text(f['statement'])) for f in event['facts']
         if f['verification_status'] == 'VERIFIED'])
    material['implications'] = sorted(
        [(i['id'], i['area'], normalized_text(i['statement']),
          normalized_text(i['assumptions']), normalized_text(i['uncertainty']))
         for i in event['implications']])
    return hashlib.sha256(_json(material).encode()).hexdigest()


def canonical_package(model):
    data = model.model_dump(mode='json')
    for collection, key in [('sources', 'id'), ('events', 'event_key'),
                            ('catalysts', 'catalyst_id'), ('theses', 'thesis_id')]:
        data[collection].sort(key=lambda item: item[key])
    data['scope']['searched_source_types'].sort()
    data['limitations'].sort()
    for event in data['events']:
        for key in ('source_ids', 'affected_segments'):
            event[key].sort()
        for key, identifier in [('facts', 'fact_key'), ('implications', 'id'),
                                ('follow_up_questions', 'id')]:
            event[key].sort(key=lambda item: item[identifier])
    for thesis in data['theses']:
        thesis['related_event_keys'].sort()
    identity = {'skill_name': 'investobot-news', 'skill_version':
                SUPPORTED_SKILLS['investobot-news'].get('skill_version', SKILL_VERSION),
                'schema_version': SUPPORTED_SKILLS['investobot-news']['schema_version'],
                'research_type': data['research_type']}
    if identity['schema_version'] != data['schema_version']:
        raise ValueError('Research contract does not match bundled skill')
    package = _json(data)
    run_id = hashlib.sha256(_json(dict(identity, package=data)).encode()).hexdigest()
    return data, package, run_id, identity


def validation_warnings(data):
    warnings = list(data['limitations'])
    if data['scope']['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('Incomplete coverage: absent stories are not resolved.')
    if not data['company'].get('cik') and not data['company'].get('security_id'):
        warnings.append('Strong company identifiers unavailable; human identity review required.')
    for event in data['events']:
        if event['event_date'] is None:
            warnings.append(f"Event date unknown: {event['event_key']}.")
        if any(f['verification_status'] == 'DISPUTED' for f in event['facts']):
            warnings.append(f"Disputed facts remain unresolved: {event['event_key']}.")
    warnings.append('Source support and real-world identity require human review; validation proves structure only.')
    return warnings


def _accepted_id(ledger, data, proposed_id):
    """Recognize identical accepted input under its original trusted skill version."""
    if ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?',
                                 (proposed_id,)).fetchone():
        return proposed_id
    versions = ledger.connection.execute(
        '''SELECT DISTINCT skill_version FROM research_runs
           WHERE research_type=? AND skill_name=? AND schema_version=?''',
        (data['research_type'], 'investobot-news', data['schema_version']))
    for (version,) in versions:
        identity = dict(skill_name='investobot-news', skill_version=version,
                        schema_version=data['schema_version'], research_type=data['research_type'])
        candidate = hashlib.sha256(_json(dict(identity, package=data)).encode()).hexdigest()
        if ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (candidate,)).fetchone():
            return candidate
    return proposed_id


def _verify_event_ownership(ledger, data, run_id=None):
    if run_id:
        run_id = _accepted_id(ledger, data, run_id)
    if run_id and ledger.connection.execute(
            'SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone():
        # The content hash pins the identical validated company and whole package.
        return
    company = dict(data['company'], company_name=data['company']['name'])
    for event in data['events']:
        rows = ledger.connection.execute(
            '''SELECT r.company_name,r.ticker,r.cik,r.security_id FROM research_news_events e
               JOIN research_runs r ON r.id=e.run_id WHERE e.event_key=?''',
            (event['event_key'],))
        for row in rows:
            prior = dict(zip(('company_name', 'ticker', 'cik', 'security_id'), row, strict=True))
            if not same_research_company(prior, company):
                raise DomainError('Event key belongs to another or unverified company; review identity', 3)


def import_research(ledger, payload, yes=False):
    from invest.news_models import NewsResearchInput

    model = NewsResearchInput.model_validate(payload)
    data, package, run_id, identity = canonical_package(model)
    run_id = _accepted_id(ledger, data, run_id)
    verify_company(ledger, data['company'])
    _verify_event_ownership(ledger, data, run_id)
    warnings = validation_warnings(data)
    compact = {'event_count': len(data['events']), 'catalyst_count': len(data['catalysts']),
               'thesis_count': len(data['theses'])}
    compact.update(fact_count=sum(len(e['facts']) for e in data['events']), warnings=warnings,
                   warning_count=len(warnings))
    exists = ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone()
    result = dict(compact, status='UNCHANGED' if exists else 'PREVIEW', committed=False,
                  research_run_id=run_id, company=data['company']['name'], mutation_scope='research')
    if not yes or exists:
        return result
    scope = data['scope']
    run = dict(id=run_id, **identity, company_name=data['company']['name'],
               ticker=data['company'].get('ticker'), cik=data['company'].get('cik'),
               security_id=data['company'].get('security_id'), fiscal_year=None, fiscal_period=None,
               period_end=scope['window_end'], researched_as_of=scope['researched_as_of'],
               imported_at=datetime.now(timezone.utc).isoformat(), coverage_status=scope['coverage_status'],
               summary_json=_json(compact), package_json=package)
    with ledger.connection:
        insert_record(ledger.connection, 'research_runs', run)
        for source in data['sources']:
            row = dict(source, run_id=run_id, source_id=source['id'], is_amendment=False,
                       is_restatement=False)
            row.pop('id')
            insert_record(ledger.connection, 'research_sources', row)
        insert_record(ledger.connection, 'research_news_scopes', dict(
            run_id=run_id, window_start=scope['window_start'], window_end=scope['window_end'],
            coverage_status=scope['coverage_status'], coverage_notes=scope['coverage_notes'],
            searched_source_types_json=_json(scope['searched_source_types'])))
        for event in data['events']:
            row = {key: value for key, value in event.items() if key not in
                   {'facts', 'source_ids', 'affected_segments', 'implications', 'follow_up_questions'}}
            row.update(run_id=run_id, material_fingerprint=material_fingerprint(event))
            for key in ('source_ids', 'affected_segments', 'implications', 'follow_up_questions'):
                row[key + '_json'] = _json(event[key])
            insert_record(ledger.connection, 'research_news_events', row)
            for fact in event['facts']:
                insert_record(ledger.connection, 'research_news_facts',
                              dict(fact, run_id=run_id, event_key=event['event_key']))
        for catalyst in data['catalysts']:
            insert_record(ledger.connection, 'research_news_catalysts', dict(catalyst, run_id=run_id))
        for thesis in data['theses']:
            row = dict(thesis, run_id=run_id, related_event_keys_json=_json(thesis['related_event_keys']))
            row.pop('related_event_keys')
            insert_record(ledger.connection, 'research_news_theses', row)
    return dict(result, status='IMPORTED', committed=True)
