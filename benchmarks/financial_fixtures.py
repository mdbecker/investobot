"""Fixed, disposable normalized financial inputs for measured public operations."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from invest.ledger import Ledger
from invest.models import SecurityInput, Snapshot, TargetInput
from invest.planning import propose, save_policy

DATE = '2026-10-10'
SOURCE_DATE = '2026-10-09'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class FinancialFixture:
    ledger: Ledger
    snapshots: list
    target_id: str
    policy: str
    prices: dict
    accounts: list
    securities: list
    counts: dict
    input_state_hash: str
    frozen: Path
    closed: bool = False

    def freeze(self):
        self.ledger.connection.commit()
        destination = sqlite3.connect(self.frozen)
        try:
            self.ledger.connection.backup(destination)
            destination.execute('PRAGMA journal_mode=DELETE')
        finally:
            destination.close()
        from benchmarks.operations import evidence
        self.input_state_hash = digest(evidence(self.ledger.planning_state()))

    def reset(self):
        self.ledger.connection.rollback()
        source = sqlite3.connect(f'file:{self.frozen}?mode=ro', uri=True)
        try:
            source.backup(self.ledger.connection)
        finally:
            source.close()

    def close(self):
        if not self.closed:
            self.ledger.connection.close()
            self.closed = True


def build(root, dimensions, *, concentrated_target=False, reuse=False):
    """Seed validated records with stable IDs; fixture writes are outside timing."""
    root = Path(root)
    metadata_path = root / 'financial-fixture.json'
    if reuse:
        if not metadata_path.is_file():
            raise ValueError('Missing financial fixture reuse metadata')
        metadata = json.loads(metadata_path.read_text())
        if metadata['dimensions'] != dimensions or metadata['concentrated_target'] != concentrated_target:
            raise ValueError('Financial fixture recipe dimensions differ')
        if not (root / 'financial.db').is_file() or not (root / 'frozen.db').is_file():
            raise ValueError('Missing financial fixture database')
        return FinancialFixture(Ledger(root / 'financial.db'), **metadata['fixture'], frozen=root / 'frozen.db')
    root.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(root / 'financial.db')
    account_count = dimensions['accounts']
    per_account = dimensions['positions'] // account_count
    if account_count * per_account != dimensions['positions']:
        raise ValueError('Position profile must divide evenly among accounts')
    accounts = [f'account-{i:03}' for i in range(account_count)]
    securities = [f'security-{i:05}' for i in range(per_account)]
    snapshots = []
    histories = dimensions['accepted_snapshots'] // account_count
    with ledger.connection:
        for i, sid in enumerate(securities):
            record = SecurityInput.model_validate(dict(ticker=f'FICT{i:05}',
                name=f'Fictional security {i}', asset_type='STOCK', currency='USD',
                source='Reviewed fictional benchmark issuer', cusip=f'{i+1:09}')).model_dump(mode='json')
            ledger.put('securities', sid, dict(record, id=sid))
        for account in accounts:
            positions = [dict(security=f'FICT{i:05}', asset_type='STOCK', quantity='10',
                price='100', market_value='1000', cost_basis='1200', as_of=SOURCE_DATE,
                displayed_price_precision=0, displayed_market_value_precision=0)
                for i in range(per_account)]
            lots = [dict(id=f'{account}:lot:{i:05}:{part}', security=f'FICT{i:05}',
                quantity='5', remaining_quantity='5', cost_basis='600', remaining_adjusted_basis='600',
                acquisition_date='2024-01-01', source_lot_id=f'fictional-{account}-{i}-{part}',
                identity_status='VERIFIED', identity_source='Reviewed fictional original lot reference',
                saleable=True) for i in range(per_account) for part in range(2)]
            payload = dict(account=dict(id=account, name=f'Fictional {account}', tax_status='TAXABLE',
                currency='USD', history_complete=True), positions=positions, lots=lots, cash='10000',
                cash_known=True, positions_complete=True, lots_complete=True,
                source_timestamp=SOURCE_DATE, data_environment='SYNTHETIC',
                source_hash=f'fictional-{account}-latest')
            payload = Snapshot.model_validate(payload).model_dump(mode='json')
            ledger.put('accounts', account, dict(payload['account'], data_environment='SYNTHETIC'))
            for observation in range(histories):
                day = (date.fromisoformat(SOURCE_DATE)-timedelta(days=histories-1-observation)).isoformat()
                snap = dict(payload, id=f'{account}:snapshot:{observation}', source_timestamp=day,
                    imported_at=day+'T12:00:00Z', source_hash=f'fictional-{account}-{day}',
                    positions=[dict(p, as_of=day) for p in payload['positions']], status='APPLIED')
                snap['fingerprint'] = digest(snap)
                ledger.put('snapshots', snap['id'], snap)
            snapshots.append(payload)
            for i, position in enumerate(payload['positions']):
                identity = f'{account}:{securities[i]}'
                ledger.put('positions', identity, dict(position, id=identity, account_id=account,
                    security_id=securities[i], source_timestamp=SOURCE_DATE, lot_state='RESOLVED'))
            for i, lot in enumerate(payload['lots']):
                ledger.put('lots', lot['id'], dict(lot, account_id=account, security_id=securities[i//2]))
            ledger.put('cash_balances', account, dict(id=account, account_id=account, amount='10000',
                as_of=SOURCE_DATE, source_timestamp=SOURCE_DATE, imported_at=SOURCE_DATE+'T12:00:00Z'))
    weight = Decimal(1)/Decimal(len(securities))
    weights = {sid: str(weight) for sid in securities}
    weights[securities[-1]] = str(Decimal(1)-weight*(len(securities)-1))
    if concentrated_target:
        weights={sid:'1' if index==0 else '0' for index,sid in enumerate(securities)}
    target = TargetInput.model_validate(dict(name='Fictional fixed target', target_allocations=weights,
        planning_constraints=dict(eligible_accounts=accounts,
            permitted_securities={account:securities for account in accounts}))).model_dump(mode='json')
    target.update(id='fictional-target',version=1,version_id='fictional-target-version-1',
                  created_at=DATE+'T12:00:00Z',updated_at=DATE+'T12:00:00Z')
    with ledger.connection:
        ledger.put('target_versions',target['version_id'],target)
        metadata={key:target[key] for key in
                  ('id','name','description','status','version','created_at','updated_at')}
        ledger.put('targets',target['id'],dict(metadata,current_version_id=target['version_id']))
    policy = dict(version='fictional-performance-v1', data_environment='SYNTHETIC', fee_per_trade='0',
        source='Explicit fictional reviewed performance-fixture policy',
        permissions={account:{sid:dict(can_buy=True,can_sell=False,can_hold=True,share_increment='1')
                              for sid in securities} for account in accounts})
    policy_id = save_policy(ledger, policy, confirm=True)['id']
    fixture = FinancialFixture(ledger, snapshots, target['id'], policy_id,
        {sid:dict(price='100',as_of=DATE,currency='USD',data_environment='SYNTHETIC',
                  source='Reviewed fictional source quote') for sid in securities}, accounts, securities,
        {key:dimensions[key] for key in ('accounts','positions','lots','accepted_snapshots')},
        '', root/'frozen.db')
    fixture.freeze()
    persist(fixture, dimensions, concentrated_target=concentrated_target)
    return fixture


def persist(fixture, dimensions, *, concentrated_target=False):
    """Store only reconstructable facts, never live database or server handles."""
    fields = ('snapshots', 'target_id', 'policy', 'prices', 'accounts', 'securities',
              'counts', 'input_state_hash')
    metadata = dict(version=1, dimensions=dimensions, concentrated_target=concentrated_target,
                    fixture={key:getattr(fixture,key) for key in fields})
    (fixture.frozen.parent / 'financial-fixture.json').write_text(json.dumps(metadata, sort_keys=True))


def seed_plans(fixture, count):
    ids = []
    for _ in range(count):
        result = propose(fixture.ledger, fixture.target_id, policy=fixture.policy,
                         mode='contributions-only', as_of=DATE, prices=fixture.prices)
        if 'id' not in result:
            raise ValueError(f'Benchmark needs a real saved successful plan: {result}')
        ids.append(result['id'])
    return ids
