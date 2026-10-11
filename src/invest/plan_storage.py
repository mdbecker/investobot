"""Focused immutable baseline/detail storage; common queries read summaries only."""

import hashlib
import json

from invest.models import DomainError


def _json(value):
    return json.dumps(value, sort_keys=True, default=str)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def save_plan(ledger, plan):
    from invest.plans import plan_summary, state_hash

    state = plan['source_state']
    from invest.db import SCHEMA_VERSION

    checksum = ledger.connection.execute(
        "SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()[0]
    plan['storage_identity'] = {'schema_version': SCHEMA_VERSION, 'manifest_hash': checksum}
    baseline_id = state_hash(state)
    details = {k: v for k, v in plan.items() if k not in {'source_state', 'source_state_hash'}}
    assumptions = plan.get('assumptions', {})
    with ledger.connection:
        ledger.connection.execute('INSERT OR IGNORE INTO plan_baselines VALUES (?, ?)',
                                  (baseline_id, _json(state)))
        ledger.connection.execute('INSERT INTO plan_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            plan['id'], baseline_id, plan['created_at'], plan['as_of'], plan['status'],
            _json(plan_summary(plan)), _json(details), _hash(assumptions.get('prices')),
            _hash(assumptions.get('tax_rates'))))


def load_plan(ledger, plan_id):
    row = ledger.connection.execute('''SELECT p.details_json, p.baseline_id, b.state_json
        FROM plan_runs p JOIN plan_baselines b ON b.id=p.baseline_id WHERE p.id=?''',
        (plan_id,)).fetchone()
    if row is None:
        raise DomainError('Plan does not exist')
    return dict(json.loads(row[0]), source_state_hash=row[1], source_state=json.loads(row[2]))


def summaries(ledger, plan_ids=None):
    where = ' WHERE id IN (' + ','.join('?' for _ in plan_ids) + ')' if plan_ids else ''
    fields = 'summary_json, baseline_id'
    if plan_ids:
        fields += ', as_of, price_assumptions_hash, tax_assumptions_hash'
    rows = ledger.connection.execute('SELECT ' + fields + ' FROM plan_runs' + where +
        ' ORDER BY created_at DESC, id DESC', plan_ids or ())
    result = []
    for row in rows:
        summary = json.loads(row[0])
        value = dict(id=summary['id'], summary=summary, source_state_hash=row[1])
        if plan_ids:
            value.update(as_of=row[2], price_assumptions_hash=row[3], tax_assumptions_hash=row[4])
        result.append(value)
    return result
