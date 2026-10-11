"""Atomic immutable research imports, isolated from financial ledger state."""

import hashlib
import json
from datetime import datetime, timezone

from invest.political_models import PoliticalResearchInput, enforce_policy
from invest.research_identity import verify_company
from invest.research_skills import SKILL_VERSION

DDL = [
    """CREATE TABLE research_political_runs (
        id TEXT PRIMARY KEY, company_name TEXT NOT NULL, ticker TEXT, security_id TEXT,
        jurisdiction TEXT NOT NULL CHECK(jurisdiction='US_FEDERAL'),
        period_start TEXT NOT NULL, period_end TEXT NOT NULL, researched_as_of TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        coverage_status TEXT NOT NULL CHECK(coverage_status IN ('COMPLETE_WITHIN_DECLARED_SCOPE','PARTIAL','BLOCKED')),
        rights_status TEXT NOT NULL CHECK(rights_status IN ('APPROVED','PENDING_REVIEW','BLOCKED')),
        limitations_json TEXT NOT NULL, unresolved_matches_json TEXT NOT NULL,
        package_json TEXT NOT NULL, FOREIGN KEY(security_id) REFERENCES securities(id))""",
    "CREATE INDEX research_political_company_idx ON research_political_runs(ticker, researched_as_of DESC)",
    """CREATE TABLE research_political_sources (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, url TEXT NOT NULL, publisher TEXT NOT NULL,
        source_type TEXT NOT NULL, published_at TEXT, accessed_at TEXT NOT NULL,
        individual_contributor_data INTEGER NOT NULL CHECK(individual_contributor_data IN (0,1)),
        rights_basis TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES research_political_runs(id),
        UNIQUE(run_id,url), UNIQUE(run_id,id))""",
    """CREATE TABLE research_political_executives (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, full_name TEXT NOT NULL, role TEXT NOT NULL,
        role_start TEXT, role_end TEXT, role_source_id TEXT NOT NULL,
        identity_status TEXT NOT NULL CHECK(identity_status='VERIFIED'),
        FOREIGN KEY(run_id) REFERENCES research_political_runs(id), UNIQUE(run_id,id),
        FOREIGN KEY(run_id,role_source_id) REFERENCES research_political_sources(run_id,id))""",
    """CREATE TABLE research_political_recipients (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, name TEXT NOT NULL,
        recipient_type TEXT NOT NULL CHECK(recipient_type IN ('CANDIDATE_COMMITTEE','PARTY_COMMITTEE','PAC','JOINT_FUNDRAISER','OTHER_COMMITTEE')),
        committee_id TEXT, candidate_id TEXT, candidate_name TEXT,
        recipient_party TEXT NOT NULL CHECK(recipient_party IN ('DEMOCRATIC','REPUBLICAN','OTHER','NONPARTISAN','UNKNOWN')),
        party_basis TEXT NOT NULL, election_cycle INTEGER, party_source_id TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES research_political_runs(id), UNIQUE(run_id,id),
        FOREIGN KEY(run_id,party_source_id) REFERENCES research_political_sources(run_id,id))""",
    """CREATE TABLE research_political_contributions (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, executive_id TEXT NOT NULL,
        recipient_id TEXT NOT NULL, transaction_date TEXT NOT NULL, amount_usd TEXT NOT NULL,
        transaction_kind TEXT NOT NULL CHECK(transaction_kind IN ('CONTRIBUTION','REFUND','REATTRIBUTION','REDESIGNATION','MEMO','OTHER')),
        channel TEXT NOT NULL CHECK(channel IN ('DIRECT','EARMARKED','COMMITTEE','UNKNOWN')),
        source_system TEXT NOT NULL, source_record_id TEXT NOT NULL, underlying_transaction_key TEXT,
        countable INTEGER NOT NULL CHECK(countable IN (0,1)), notes TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(run_id) REFERENCES research_political_runs(id), UNIQUE(run_id,id),
        FOREIGN KEY(run_id,executive_id) REFERENCES research_political_executives(run_id,id),
        FOREIGN KEY(run_id,recipient_id) REFERENCES research_political_recipients(run_id,id),
        UNIQUE(run_id,source_system,source_record_id),
        CHECK(countable=0 OR underlying_transaction_key IS NOT NULL))""",
    "CREATE UNIQUE INDEX research_political_counted_once_idx ON research_political_contributions(run_id,underlying_transaction_key) WHERE countable=1",
    "CREATE INDEX research_political_executive_idx ON research_political_contributions(executive_id,transaction_date)",
    """CREATE TABLE research_political_evidence (
        contribution_id TEXT NOT NULL, source_id TEXT NOT NULL, run_id TEXT NOT NULL,
        PRIMARY KEY(contribution_id,source_id),
        FOREIGN KEY(run_id,contribution_id) REFERENCES research_political_contributions(run_id,id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_political_sources(run_id,id))""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def import_research(ledger, payload, yes=False, policy_path=None):
    model = PoliticalResearchInput.model_validate(payload)
    enforce_policy(model, policy_path)
    data = model.model_dump(mode='json')
    data.update(skill_name='investobot-political-contributions', skill_version=SKILL_VERSION)
    # Sort identified collections so an external agent's ordering is not identity.
    for collection in ('sources', 'executives', 'recipients', 'contributions'):
        data[collection].sort(key=lambda item: item['id'])
    for contribution in data['contributions']:
        # Preserve historical executive package identities when new optional
        # category/linkage fields were absent from the original interchange.
        for field in ('contributor_category', 'corporate_pac_identity_evidence'):
            if contribution[field] is None:
                contribution.pop(field)
        contribution['source_ids'].sort()
        value = contribution['amount_usd']
        # Plain strings preserve every significant digit beyond context precision.
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        contribution['amount_usd'] = '0' if value in {'-0', '0'} else value
    package = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    run_id = hashlib.sha256(package.encode()).hexdigest()
    security_id = data['company'].get('security_id')
    verify_company(ledger, data['company'])
    exists = ledger.connection.execute('SELECT 1 FROM research_political_runs WHERE id=?', (run_id,)).fetchone()
    result = {'research_run_id': run_id, 'status': 'UNCHANGED' if exists else 'PREVIEW',
              'committed': False, 'mutation_scope': 'research',
              'verified_transactions': len(data['contributions']),
              'coverage_status': data['scope']['coverage_status'],
              'rights_status': data['scope']['rights_status'], 'limitations': data['limitations']}
    if not yes or exists:
        return result
    scoped = lambda key: f'{run_id}:{key}'
    with ledger.connection:
        ledger.connection.execute('INSERT INTO research_political_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (run_id, data['company']['name'], data['company'].get('ticker'), security_id,
             data['scope']['jurisdiction'], data['scope']['period_start'], data['scope']['period_end'],
             data['scope']['researched_as_of'], datetime.now(timezone.utc).isoformat(),
             data['scope']['coverage_status'], data['scope']['rights_status'],
             json.dumps(data['limitations']), json.dumps(data['unresolved_matches']), package))
        for source in data['sources']:
            ledger.connection.execute('INSERT INTO research_political_sources VALUES (?,?,?,?,?,?,?,?,?)',
                (scoped(source['id']), run_id, source['url'], source['publisher'], source['source_type'],
                 source['published_at'], source['accessed_at'], source['individual_contributor_data'], source['rights_basis']))
        for executive in data['executives']:
            ledger.connection.execute('INSERT INTO research_political_executives VALUES (?,?,?,?,?,?,?,?)',
                (scoped(executive['id']), run_id, executive['full_name'], executive['role'],
                 executive['role_start'], executive['role_end'], scoped(executive['role_source_id']), executive['identity_status']))
        for recipient in data['recipients']:
            ledger.connection.execute('INSERT INTO research_political_recipients VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (scoped(recipient['id']), run_id, recipient['name'], recipient['recipient_type'],
                 recipient['committee_id'], recipient['candidate_id'], recipient['candidate_name'],
                 recipient['recipient_party'], recipient['party_basis'], recipient['election_cycle'], scoped(recipient['party_source_id'])))
        for contribution in data['contributions']:
            ledger.connection.execute('INSERT INTO research_political_contributions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (scoped(contribution['id']), run_id, scoped(contribution['executive_id']), scoped(contribution['recipient_id']),
                 contribution['date'], contribution['amount_usd'], contribution['transaction_kind'],
                 contribution['channel'], contribution['source_system'], contribution['source_record_id'],
                 contribution['underlying_transaction_key'], contribution['countable'], contribution['notes']))
            for source_id in contribution['source_ids']:
                ledger.connection.execute('INSERT INTO research_political_evidence VALUES (?,?,?)',
                    (scoped(contribution['id']), scoped(source_id), run_id))
    return dict(result, status='IMPORTED', committed=True)
