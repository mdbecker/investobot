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
    baseline_id = state_hash(state)
    details = {k: v for k, v in plan.items() if k not in {'source_state', 'source_state_hash'}}
    assumptions = plan.get('assumptions', {})
    with ledger.connection:
        ledger.connection.execute('INSERT OR IGNORE INTO plan_baselines VALUES (?, ?)',
                                  (baseline_id, _json(state)))
        ledger.connection.execute('INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            plan['id'], baseline_id, plan['created_at'], plan['as_of'], plan['status'],
            _json(plan_summary(plan)), _json(details), _hash(assumptions.get('prices')),
            _hash(assumptions.get('tax_rates'))))


def load_plan(ledger, plan_id):
    row = ledger.connection.execute('''SELECT p.details_json, p.baseline_id, b.state_json
        FROM plans p JOIN plan_baselines b ON b.id=p.baseline_id WHERE p.id=?''',
        (plan_id,)).fetchone()
    if row is None:
        raise DomainError('Plan does not exist')
    return dict(json.loads(row[0]), source_state_hash=row[1], source_state=json.loads(row[2]))


def summaries(ledger, plan_ids=None):
    where = ' WHERE id IN (' + ','.join('?' for _ in plan_ids) + ')' if plan_ids else ''
    rows = ledger.connection.execute('''SELECT summary_json, baseline_id, as_of,
        price_assumptions_hash, tax_assumptions_hash FROM plans''' + where +
        ' ORDER BY created_at DESC, id DESC', plan_ids or ())
    return [dict(id=(summary := json.loads(r[0]))['id'], summary=summary,
                 source_state_hash=r[1], as_of=r[2], price_assumptions_hash=r[3],
                 tax_assumptions_hash=r[4]) for r in rows]
