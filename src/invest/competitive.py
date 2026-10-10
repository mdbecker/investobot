"""Immutable competitive evidence, independent of financial and planning state."""

import json
from datetime import datetime, timezone

from invest.competitive_models import CompetitiveResearchInput
from invest.research_identity import verify_company
from invest.research_skills import SUPPORTED_SKILLS
from invest.research_storage import canonical_json_hash, decimal_text, insert_record

DDL = [
    """CREATE TABLE research_competitive_entities (
        run_id TEXT NOT NULL, entity_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('SUBJECT','PEER')),
        name TEXT NOT NULL, ticker TEXT, cik TEXT, security_id TEXT,
        relationship TEXT, rationale TEXT, selection_source_id TEXT,
        PRIMARY KEY(run_id,entity_id),
        FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(security_id) REFERENCES securities(id),
        FOREIGN KEY(run_id,selection_source_id) REFERENCES research_sources(run_id,source_id),
        CHECK((role='SUBJECT' AND entity_id='subject' AND relationship IS NULL
               AND selection_source_id IS NULL)
           OR (role='PEER' AND entity_id<>'subject' AND relationship IS NOT NULL
               AND selection_source_id IS NOT NULL)))""",
    """CREATE TABLE research_competitive_overlaps (
        run_id TEXT NOT NULL, overlap_id TEXT NOT NULL, peer_id TEXT NOT NULL,
        market TEXT NOT NULL, geography TEXT NOT NULL,
        subject_segment TEXT NOT NULL, peer_segment TEXT NOT NULL,
        overlap_type TEXT NOT NULL CHECK(overlap_type IN ('DIRECT','PARTIAL','POTENTIAL')),
        description TEXT NOT NULL, uncertainty TEXT NOT NULL,
        subject_source_id TEXT NOT NULL, peer_source_id TEXT NOT NULL,
        PRIMARY KEY(run_id,overlap_id),
        FOREIGN KEY(run_id,peer_id) REFERENCES research_competitive_entities(run_id,entity_id),
        FOREIGN KEY(run_id,subject_source_id) REFERENCES research_sources(run_id,source_id),
        FOREIGN KEY(run_id,peer_source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_competitive_findings (
        run_id TEXT NOT NULL, finding_id TEXT NOT NULL, peer_id TEXT NOT NULL,
        overlap_id TEXT, kind TEXT NOT NULL CHECK(kind IN
          ('SUBJECT_ADVANTAGE','SUBJECT_DISADVANTAGE','TRADEOFF','UNRESOLVED')),
        factual_basis TEXT NOT NULL, interpretation TEXT NOT NULL,
        assumptions TEXT NOT NULL, uncertainty TEXT NOT NULL,
        source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        corroborating_source_ids_json TEXT NOT NULL,
        PRIMARY KEY(run_id,finding_id),
        FOREIGN KEY(run_id,peer_id) REFERENCES research_competitive_entities(run_id,entity_id),
        FOREIGN KEY(run_id,overlap_id) REFERENCES research_competitive_overlaps(run_id,overlap_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_competitive_metrics (
        run_id TEXT NOT NULL, metric_id TEXT NOT NULL, entity_id TEXT NOT NULL,
        metric_code TEXT NOT NULL, metric_definition TEXT NOT NULL,
        value_text TEXT NOT NULL, unit TEXT NOT NULL, accounting_basis TEXT NOT NULL,
        period_type TEXT NOT NULL CHECK(period_type IN ('INSTANT','DURATION')),
        period_start TEXT, period_end TEXT NOT NULL,
        scope TEXT NOT NULL CHECK(scope IN ('CONSOLIDATED','SEGMENT')),
        segment_name TEXT, overlap_id TEXT, source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        PRIMARY KEY(run_id,metric_id),
        FOREIGN KEY(run_id,entity_id) REFERENCES research_competitive_entities(run_id,entity_id),
        FOREIGN KEY(run_id,overlap_id) REFERENCES research_competitive_overlaps(run_id,overlap_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id),
        CHECK((period_type='INSTANT' AND period_start IS NULL)
           OR (period_type='DURATION' AND period_start IS NOT NULL)),
        CHECK((scope='CONSOLIDATED' AND segment_name IS NULL AND overlap_id IS NULL)
           OR (scope='SEGMENT' AND segment_name IS NOT NULL)))""",
    """CREATE INDEX research_competitive_metric_entity_idx
       ON research_competitive_metrics(run_id,entity_id,metric_code)""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def canonical_package(model):
    """Domain-specific normalization; earlier research hash semantics stay intact."""
    model = CompetitiveResearchInput.model_validate(model)
    data = model.model_dump(mode='json')
    for name in ('sources', 'overlaps', 'findings', 'metrics'):
        data[name].sort(key=lambda item: item['id'])
    data['peers'].sort(key=lambda item: item['entity_id'])
    data['limitations'].sort()
    for finding in data['findings']:
        finding['corroborating_source_ids'].sort()
    for metric in data['metrics']:
        metric['value'] = decimal_text(metric['value'])
    skill_name = 'investobot-competitive'
    entry = SUPPORTED_SKILLS[skill_name]
    identity = {'skill_name': skill_name, 'skill_version': entry['skill_version'],
                'schema_version': entry['schema_version'], 'research_type': data['research_type']}
    package, run_id = canonical_json_hash(data, identity)
    return data, package, run_id, identity


def verify_entities(ledger, data):
    for entity in [data['subject'], *data['peers']]:
        verify_company(ledger, entity)


def validation_warnings(data):
    warnings = list(data['limitations'])
    if data['scope']['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('Research coverage is incomplete; missing disclosures remain unknown.')
    warnings.append('Citations require independent human source review; market competition '
                    'does not establish investment suitability.')
    for entity in [data['subject'], *data['peers']]:
        if not entity.get('cik'):
            warnings.append(f"Issuer CIK unknown for {entity['entity_id']}; verify legal identity.")
        if not any(metric['entity_id'] == entity['entity_id'] for metric in data['metrics']):
            warnings.append(f"Reported metrics unavailable for {entity['entity_id']}.")
    return warnings


def import_research(ledger, payload, yes=False):
    data, package, run_id, identity = canonical_package(payload)
    verify_entities(ledger, data)
    warnings = validation_warnings(data)
    compact = {f'{key[:-1]}_count': len(data[key]) for key in ('peers', 'overlaps', 'findings', 'metrics')}
    compact.update(warnings=warnings, limitations=data['limitations'], scope=data['scope'])
    exists = ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone()
    result = {'status': 'UNCHANGED' if exists else 'PREVIEW', 'committed': False,
              'run_id': run_id, 'research_run_id': run_id,
              **{key: value for key, value in compact.items() if key.endswith('_count')},
              'warnings': warnings, 'mutation_scope': 'research'}
    if not yes or exists:
        return result
    subject = data['subject']
    run = dict(id=run_id, **identity, company_name=subject['name'], ticker=subject['ticker'],
               security_id=subject['security_id'], cik=subject['cik'], fiscal_year=None,
               fiscal_period=None, period_end=None, researched_as_of=data['scope']['researched_as_of'],
               imported_at=datetime.now(timezone.utc).isoformat(),
               coverage_status=data['scope']['coverage_status'], summary_json=json.dumps(compact),
               package_json=package)
    with ledger.connection:
        insert_record(ledger.connection, 'research_runs', run)
        for source in data['sources']:
            row = dict(source, run_id=run_id, source_id=source['id'],
                       is_amendment=False, is_restatement=False)
            row.pop('id')
            insert_record(ledger.connection, 'research_sources', row)
        for entity in [subject, *data['peers']]:
            role = 'SUBJECT' if entity['entity_id'] == 'subject' else 'PEER'
            insert_record(ledger.connection, 'research_competitive_entities',
                          dict(entity, run_id=run_id, role=role))
        for overlap in data['overlaps']:
            row = dict(overlap, run_id=run_id, overlap_id=overlap['id'])
            row.pop('id')
            insert_record(ledger.connection, 'research_competitive_overlaps', row)
        for finding in data['findings']:
            row = dict(finding, run_id=run_id, finding_id=finding['id'],
                       corroborating_source_ids_json=json.dumps(finding['corroborating_source_ids']))
            row.pop('id')
            row.pop('corroborating_source_ids')
            insert_record(ledger.connection, 'research_competitive_findings', row)
        for metric in data['metrics']:
            row = dict(metric, run_id=run_id, metric_id=metric['id'], value_text=metric['value'])
            row.pop('id')
            row.pop('value')
            insert_record(ledger.connection, 'research_competitive_metrics', row)
    return dict(result, status='IMPORTED', committed=True)
