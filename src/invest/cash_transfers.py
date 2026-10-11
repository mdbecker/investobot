"""Explicitly reviewed paired cash movements; never infer a missing transfer leg."""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from invest.db import text_decimal
from invest.models import DomainError, Snapshot


class CashTransferInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transfer_id: str = Field(min_length=1)
    from_account_id: str = Field(min_length=1)
    to_account_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(min_length=1)
    data_environment: Literal['REAL', 'SYNTHETIC']
    event_timestamp: str
    source: str = Field(min_length=1)

    @field_validator('amount', mode='before')
    @classmethod
    def exact_amount(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('Transfer amounts require exact decimal strings')
        return value

    @field_validator('event_timestamp')
    @classmethod
    def precise_timestamp(cls, value):
        value = Snapshot.valid_source_timestamp(value)
        if value is None or len(value) <= 10:
            raise ValueError('Linked transfers require a verified event timestamp')
        return value


def _fail(code, message, exit_code=3):
    error = DomainError(message, exit_code)
    error.result = {'status': 'BLOCKED', 'issues': [{'code': code,
        'message': message, 'blocks_calculation': True, 'blocks_proposals': True,
        'blocks_execution_review': True}]}
    raise error


def record(ledger, payload, *, confirm=False):
    try:
        submitted = CashTransferInput.model_validate(payload).model_dump(mode='json')
    except ValidationError as error:
        _fail('INVALID_CASH_TRANSFER', str(error), 1)
    submitted['amount'] = text_decimal(submitted['amount'])
    # Serialize accepted financial changes and idempotency checks together.
    with ledger.connection:
        if confirm:
            ledger.connection.execute('BEGIN IMMEDIATE')
        return _record(ledger, submitted, confirm)


def _record(ledger, submitted, confirm):
    source_id, destination_id = submitted['from_account_id'], submitted['to_account_id']
    if source_id == destination_id:
        _fail('INVALID_TRANSFER_ACCOUNTS', 'Transfer legs require two distinct accounts')
    state = ledger.state()
    accounts = {row['id']: row for row in state['accounts']}
    if {source_id, destination_id} - accounts.keys():
        _fail('UNKNOWN_TRANSFER_ACCOUNT', 'Both transfer accounts must already be accepted')
    for identity in (source_id, destination_id):
        account = accounts[identity]
        if account.get('currency') != submitted['currency']:
            _fail('UNSUPPORTED_CURRENCY', 'Both legs require the same confirmed currency; no FX model exists')
        if account.get('data_environment') != submitted['data_environment']:
            _fail('MIXED_DATA_ENVIRONMENT', 'Transfer provenance must match both accepted accounts')
    digest = hashlib.sha256(submitted['transfer_id'].encode()).hexdigest()
    legs = []
    for identity, kind, suffix in ((source_id, 'CASH_WITHDRAWAL', 'out'),
                                  (destination_id, 'CASH_DEPOSIT', 'in')):
        identifier = f'cash-transfer:{digest}:{suffix}'
        legs.append({'id': identifier, 'activity_id': identifier, 'account_id': identity,
            'type': kind, 'date': submitted['event_timestamp'][:10],
            'event_timestamp': submitted['event_timestamp'], 'amount': submitted['amount'],
            'source': submitted['source'], 'currency': submitted['currency'],
            'data_environment': submitted['data_environment'],
            'classification': 'INTERNAL_TRANSFER', 'transfer_id': submitted['transfer_id']})
    existing = [row for row in state['activities'] if row.get('transfer_id') == submitted['transfer_id']]
    if existing:
        stored = {row['id']: {key: row.get(key) for key in legs[0]} for row in existing}
        if stored != {row['id']: row for row in legs}:
            _fail('TRANSFER_ID_CONFLICT', 'Transfer ID already has different confirmed facts')
        return {'status': 'UNCHANGED', 'committed': False, 'transfer_id': submitted['transfer_id']}
    if any(row['id'] in {leg['id'] for leg in legs} for row in state['activities']):
        _fail('TRANSFER_ID_CONFLICT', 'Transfer leg IDs conflict with existing confirmed activity')
    cash = {row['account_id']: row for row in state['cash_balances']}
    if {source_id, destination_id} - cash.keys():
        _fail('UNKNOWN_CASH_COVERAGE', 'Both accounts require confirmed cash before a transfer')
    event = datetime.fromisoformat(submitted['event_timestamp'].replace('Z', '+00:00'))
    for identity in (source_id, destination_id):
        dates = [cash[identity].get('source_timestamp') or cash[identity].get('as_of')]
        dates.extend(row.get('event_timestamp') or row['date'] for row in state['activities']
                     if row['account_id'] == identity)
        for timestamp in dates:
            if not timestamp:
                _fail('UNKNOWN_CASH_CHRONOLOGY', 'Confirm the cash source date before recording a transfer')
            if len(timestamp) == 10:
                if timestamp >= event.date().isoformat():
                    _fail('AMBIGUOUS_EVENT_ORDER', 'Transfer must follow the confirmed cash checkpoint and events')
            elif datetime.fromisoformat(timestamp.replace('Z', '+00:00')) >= event:
                _fail('AMBIGUOUS_EVENT_ORDER', 'Transfer must follow the confirmed cash checkpoint and events')
    amount = Decimal(submitted['amount'])
    balances = [Decimal(cash[identity]['amount']) for identity in (source_id, destination_id)]
    if balances[0] < amount:
        _fail('INSUFFICIENT_CONFIRMED_CASH', 'Transfer exceeds confirmed source-account cash')
    with localcontext() as context:
        context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                   for number in [amount, *balances]) + 64)
        final = [balances[0] - amount, balances[1] + amount]
    if confirm:
        for identity, value in zip((source_id, destination_id), final, strict=True):
            ledger.put('cash_balances', cash[identity]['id'], dict(cash[identity],
                amount=text_decimal(value), as_of=submitted['event_timestamp'],
                source_timestamp=submitted['event_timestamp']))
        for leg in legs:
            ledger.put('activities', leg['id'], dict(leg, recorded_at=datetime.now(timezone.utc).isoformat()))
    return {'status': 'RECORDED' if confirm else 'PREVIEW', 'committed': confirm,
            'transfer_id': submitted['transfer_id'], 'legs': legs}
