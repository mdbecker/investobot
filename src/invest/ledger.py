"""Small explicit SQLite ledger; mutations are atomic and preserve normalized audit history."""
import copy
import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from invest.models import Snapshot, DomainError, decimal

TABLES = ['accounts', 'securities', 'positions', 'lots', 'cash_balances', 'activities', 'snapshots', 'market_data_cache', 'fund_holdings_cache', 'trade_proposals']

class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute('PRAGMA foreign_keys=ON')
        version = self.connection.execute('PRAGMA user_version').fetchone()[0]
        if version > 1:
            raise DomainError('Database schema is newer than this application', 3)
        if version == 0:
            with self.connection:
                for table in TABLES:
                    self.connection.execute(f'CREATE TABLE {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
                self.connection.execute('PRAGMA user_version=1')

    def rows(self, table):
        if table not in TABLES:
            raise ValueError('Unknown table')
        return [json.loads(r[0]) for r in self.connection.execute(f'SELECT data FROM {table} ORDER BY id')]

    def put(self, table, key, data):
        if table not in TABLES:
            raise ValueError('Unknown table')
        self.connection.execute(f'INSERT OR REPLACE INTO {table} VALUES (?, ?)', (key, json.dumps(data, default=str)))

    def state(self):
        return {table: self.rows(table) for table in ['accounts', 'securities', 'positions', 'lots', 'cash_balances', 'activities', 'snapshots']}

    def resolve(self, alias):
        matches = [s for s in self.rows('securities') if alias in {s['id'], s.get('ticker'), s.get('cusip'), s.get('isin'), s.get('figi')}]
        if len(matches) != 1:
            raise DomainError('Security is unknown or ambiguous', 3)
        return matches[0]

    def reconcile(self, snapshot):
        snapshot = Snapshot.model_validate(snapshot).model_dump(mode='json')
        account_id = snapshot['account']['id']
        old = {p['security']: p for p in self.rows('positions') if p['account_id'] == account_id}
        changes = []
        incoming = {p['security']: p for p in snapshot['positions']}
        for security in sorted(old.keys() | incoming.keys()):
            if security not in old or security not in incoming:
                changes.append({'kind': 'new_position' if security not in old else 'removed_position', 'security': security})
            elif decimal(old[security]['quantity']) != decimal(incoming[security]['quantity']):
                changes.append({'kind': 'quantity', 'security': security, 'before': old[security]['quantity'], 'after': incoming[security]['quantity']})
        current_cash = next((c for c in self.rows('cash_balances') if c['account_id'] == account_id), None)
        if snapshot['cash_known'] and (not current_cash or decimal(current_cash['amount']) != decimal(snapshot['cash'])):
            changes.append({'kind': 'cash', 'before': current_cash['amount'] if current_cash else None, 'after': snapshot['cash']})
        old_lots = [{k: v for k, v in lot.items() if k not in {'account_id', 'security_id'}} for lot in self.rows('lots') if lot['account_id'] == account_id]
        if old_lots != snapshot['lots']:
            changes.append({'kind': 'lots'})
        known = {s['ticker'] for s in self.rows('securities')}
        return {'account_id': account_id, 'changes': changes, 'unidentified_securities': sorted(incoming.keys() - known), 'warnings': snapshot['warnings'] + (['State differences do not establish transactions'] if changes else [])}

    def apply(self, snapshot):
        snap = Snapshot.model_validate(snapshot).model_dump(mode='json')
        account_id = snap['account']['id']
        if len({p['security'] for p in snap['positions']}) != len(snap['positions']):
            raise DomainError('Duplicate positions must be resolved before apply', 3)
        for lot in snap['lots']:
            if decimal(lot['remaining_quantity']) > decimal(lot['quantity']):
                raise DomainError('Lot remaining quantity exceeds original quantity', 3)
        for symbol in {lot['security'] for lot in snap['lots']}:
            position = next((p for p in snap['positions'] if p['security'] == symbol), None)
            remaining = sum((decimal(l['remaining_quantity']) for l in snap['lots'] if l['security'] == symbol), Decimal('0'))
            if position is None or remaining > decimal(position['quantity']):
                raise DomainError('Lot quantities exceed imported position', 3)
        with self.connection:
            self.put('accounts', account_id, snap['account'])
            for table in ['positions', 'lots']:
                for item in self.rows(table):
                    if item['account_id'] == account_id:
                        self.connection.execute(f'DELETE FROM {table} WHERE id=?', (item['id'],))
            for p in snap['positions']:
                existing = [s for s in self.rows('securities') if s['ticker'] == p['security']]
                sid = existing[0]['id'] if existing else str(uuid.uuid4())
                security = existing[0] if existing else {'id': sid, 'ticker': p['security'], 'name': p['name'], 'asset_type': p['asset_type'], 'currency': snap['account']['currency'], 'cusip': None, 'isin': None, 'figi': None}
                self.put('securities', sid, security)
                p = dict(p, id=f'{account_id}:{sid}', account_id=account_id, security_id=sid)
                self.put('positions', p['id'], p)
            for lot in snap['lots']:
                sid = self.resolve(lot['security'])['id']
                lot = dict(lot, account_id=account_id, security_id=sid)
                self.put('lots', lot['id'], lot)
            if snap['cash_known']:
                self.put('cash_balances', account_id, {'id': account_id, 'account_id': account_id, 'amount': snap['cash'], 'as_of': snap['source_timestamp'] or snap['imported_at']})
            audit_id = str(uuid.uuid4())
            self.put('snapshots', audit_id, dict(snap, id=audit_id))
        return {'status': 'APPLIED', 'snapshot_id': audit_id, 'account_id': account_id, 'warnings': snap['warnings']}

    def summary(self):
        return summarize(self.state())

    def record_activity(self, activity, yes=False):
        state = self.state()
        changed, result = activity_change(state, activity)
        if yes:
            with self.connection:
                for table in ['positions', 'cash_balances', 'lots']:
                    for item in changed[table]:
                        self.put(table, item['id'], item)
                aid = str(uuid.uuid4())
                self.put('activities', aid, dict(activity, id=aid))
        return dict(result, status='RECORDED' if yes else 'PREVIEW', committed=yes)


def summarize(state):
    cash = sum((decimal(c['amount']) for c in state['cash_balances']), Decimal('0'))
    value = sum((decimal(p['market_value']) for p in state['positions']), cash)
    accounts, taxes, allocation = {}, {}, {'CASH': str(cash)}
    warnings = []
    for a in state['accounts']:
        total = sum((decimal(p['market_value']) for p in state['positions'] if p['account_id'] == a['id']), Decimal('0'))
        total += sum((decimal(c['amount']) for c in state['cash_balances'] if c['account_id'] == a['id']), Decimal('0'))
        accounts[a['id']] = str(total)
        taxes[a['tax_status']] = str(decimal(taxes.get(a['tax_status'], '0')) + total)
    unrealized = Decimal('0')
    for p in state['positions']:
        asset = p.get('asset_type', 'OTHER')
        allocation[asset] = str(decimal(allocation.get(asset, '0')) + decimal(p['market_value']))
        if p.get('cost_basis') is None:
            warnings.append(f"{p['security']}: basis unavailable")
        else:
            unrealized += decimal(p['market_value']) - decimal(p['cost_basis'])
    return {'total_value': str(value), 'cash': str(cash), 'by_account': accounts, 'by_tax_status': taxes, 'allocation': allocation, 'largest_positions': sorted(state['positions'], key=lambda p: decimal(p['market_value']), reverse=True)[:10], 'unrealized_gain_loss_known_basis': str(unrealized), 'snapshot_dates': sorted({p['as_of'] for p in state['positions']}), 'warnings': warnings}


def activity_change(state, activity):
    state = copy.deepcopy(state)
    account_id, kind = activity['account_id'], activity['type'].upper()
    account = next((a for a in state['accounts'] if a['id'] == account_id), None)
    if not account:
        raise DomainError('Account does not exist')
    date.fromisoformat(activity['date'])
    if kind not in {'BUY', 'SELL', 'TRANSFER_IN', 'TRANSFER_OUT', 'DIVIDEND', 'INTEREST', 'FEE', 'CASH_DEPOSIT', 'CASH_WITHDRAWAL'}:
        raise DomainError('Unsupported activity type')
    cash = next((c for c in state['cash_balances'] if c['account_id'] == account_id), None)
    if not cash:
        raise DomainError('Cash balance is unknown', 3)
    delta = Decimal('0')
    if kind in {'BUY', 'SELL', 'TRANSFER_IN', 'TRANSFER_OUT'}:
        qty, price, fee = decimal(activity['quantity']), decimal(activity['price']), decimal(activity.get('fee', 0))
        if qty <= 0 or price < 0 or fee < 0:
            raise DomainError('Quantity must be positive; price and fee nonnegative')
        security = next((s for s in state['securities'] if activity['security'] in {s['id'], s['ticker']}), None)
        if not security:
            raise DomainError('Security does not resolve')
        p = next((p for p in state['positions'] if p['account_id'] == account_id and p['security_id'] == security['id']), None)
        if p is None:
            p = dict(id=f"{account_id}:{security['id']}", account_id=account_id, security_id=security['id'], security=security['ticker'], name=security['name'], asset_type=security['asset_type'], quantity='0', market_value='0', cost_basis=None)
            state['positions'].append(p)
        selling = kind in {'SELL', 'TRANSFER_OUT'}
        if selling and qty > decimal(p['quantity']):
            raise DomainError('Sale/transfer exceeds known position', 3)
        p['quantity'] = str(decimal(p['quantity']) + (-qty if selling else qty))
        p['price'], p['market_value'], p['as_of'] = str(price), str(decimal(p['quantity']) * price), activity['date']
        if kind == 'BUY':
            delta = -(qty * price + fee)
            lid = str(uuid.uuid4())
            state['lots'].append(dict(id=lid, account_id=account_id, security_id=security['id'], security=security['ticker'], acquisition_date=activity['date'], quantity=str(qty), remaining_quantity=str(qty), cost_basis=str(qty * price + fee)))
        elif kind == 'SELL':
            delta = qty * price - fee
        if selling:
            remaining = qty
            for lot in sorted(state['lots'], key=lambda l: l['acquisition_date']):
                if lot['account_id'] == account_id and lot['security_id'] == security['id']:
                    used = min(remaining, decimal(lot['remaining_quantity']))
                    lot['remaining_quantity'] = str(decimal(lot['remaining_quantity']) - used)
                    remaining -= used
            p['cost_basis'] = None  # source snapshot remains authoritative
    else:
        amount = decimal(activity['amount'])
        if amount <= 0:
            raise DomainError('Amount must be positive')
        delta = -amount if kind in {'FEE', 'CASH_WITHDRAWAL'} else amount
    after_cash = decimal(cash['amount']) + delta
    if after_cash < 0:
        raise DomainError('Insufficient cash', 3)
    cash['amount'] = str(after_cash)
    return state, {'cash_change': str(delta), 'cash_after': str(after_cash), 'warnings': ['Recorded activities do not establish complete household transaction history']}
