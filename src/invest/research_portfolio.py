"""Frozen issuer research queues and factual, coverage-aware evidence summaries."""

import copy
import hashlib
import importlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal, localcontext

from invest.models import DomainError
from invest.research_skills import SKILL_VERSION, SUPPORTED_SKILLS

STATUSES = {'AVAILABLE', 'PARTIAL', 'REVIEW_REQUIRED', 'NOT_RESEARCHED'}
CATEGORIES = {'EXECUTIVE_PERSONAL', 'EMPLOYEE_PERSONAL', 'CORPORATE_PAC'}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise DomainError('Research financial projections require exact plain decimal strings')
    return Decimal(value)


def _text(value):
    value = format(value, 'f')
    value = value.rstrip('0').rstrip('.') if '.' in value else value
    return '0' if value == '-0' else value


def _date(value):
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Noncanonical date')
        return date.fromisoformat(value)
    except (ValueError, TypeError) as error:
        raise DomainError('Research cutoff/window requires an ISO calendar date') from error


def _issue(code, message, *ids):
    return {'code': code, 'severity': 'WARNING', 'affected_ids': list(ids),
            'blocks_calculation': False, 'blocks_proposal': True,
            'blocks_execution_review': True, 'message': message}


def freeze_universe(universe, *, requested_top=20, as_of):
    """Adapt sourced look-through companies without normalizing partial coverage."""
    _date(as_of)
    if isinstance(requested_top, bool) or not isinstance(requested_top, int) or requested_top < 1:
        raise DomainError('Requested research top must be a positive integer')
    if universe.get('data_environment') not in {'REAL', 'SYNTHETIC'}:
        raise DomainError('Frozen research universe needs explicit data environment', 3)
    if universe.get('as_of') != as_of:
        raise DomainError('Frozen research cutoff differs from source universe', 3)
    if not universe.get('currency'):
        raise DomainError('Research exposure needs one verified currency', 3)
    total = _decimal(universe.get('household_total_value', universe.get('total_value')))
    if total <= 0:
        raise DomainError('Research weights need a positive whole-household denominator', 3)
    companies = universe.get('companies', [])[:requested_top]
    identities = [row.get('issuer_id') for row in companies]
    if any(not identity for identity in identities) or len(identities) != len(set(identities)):
        raise DomainError('Research universe issuer identities must be present and unique', 3)
    issuers = []
    with localcontext() as context:
        context.prec = max(80, len(str(total)) + sum(len(row['total_value']) for row in companies))
        for company in companies:
            amount = _decimal(company['total_value'])
            if amount < 0:
                raise DomainError('Underlying research exposure cannot be negative', 3)
            issuers.append(dict(copy.deepcopy(company), exposure_weight=_text(amount / total)))
    coverage = copy.deepcopy(universe.get('coverage', {}))
    coverage['household_total_value'] = _text(total)
    for key in ('unknown_exposure_value', 'filtered_exposure_value', 'stale_exposure_value',
                'unresolved_issuer_value', 'detected_company_count', 'selected_company_count'):
        if key in universe:
            coverage[key] = copy.deepcopy(universe[key])
    frozen = {'as_of': as_of, 'data_environment': universe['data_environment'],
              'currency': universe['currency'], 'requested_top': requested_top,
              'issuers': issuers, 'coverage': coverage,
              'source_manifest_ids': list(universe.get('source_manifest_ids', [])),
              'issues': copy.deepcopy(universe.get('issues', []))}
    if universe.get('manifest_id'):
        frozen['source_manifest_ids'] = list(dict.fromkeys(
            [*frozen['source_manifest_ids'], universe['manifest_id']]))
    frozen['manifest_id'] = 'research-universe-' + _hash(frozen)
    return frozen


def _events(observations, window_start):
    grouped = {}
    for observation in observations:
        for event in observation.get('events', []):
            key = event.get('event_key')
            if not isinstance(key, str) or not key:
                raise DomainError('Research event identity must be explicit')
            citations = list(event.get('source_ids', []))
            if event.get('source_id'):
                citations.append(event['source_id'])
            if not citations:
                raise DomainError('Research event needs cited source identity')
            if key not in grouped:
                grouped[key] = dict(copy.deepcopy(event), source_ids=[], observations=[])
            row = grouped[key]
            row['source_ids'] = sorted(set([*row['source_ids'], *citations]))
            row['observations'].append(copy.deepcopy(event))
            # Different stories never prove a closure. Keep all disputed/terminal
            # observations, including dates and citations, without voting truth.
            if event.get('event_status') in {'DISPUTED', 'NOT_REOBSERVED'}:
                row['event_status'] = event['event_status']
            if event.get('event_date') and window_start:
                row['predates_window'] = _date(event['event_date']) < _date(window_start)
    return [grouped[key] for key in sorted(grouped)]


def _political(observations, issuer_id):
    totals, issues, excluded, seen = {}, [], 0, {}
    amounts = [contribution.get('amount', '') for observation in observations
               for contribution in observation.get('political', [])]
    with localcontext() as precision:
        precision.prec = max(80, sum(len(value) for value in amounts))
        return _political_exact(observations, issuer_id, totals, issues, excluded, seen)


def _political_exact(observations, issuer_id, totals, issues, excluded, seen):
    for observation in observations:
        for contribution in observation.get('political', []):
            category = contribution.get('category')
            identifier = contribution.get('id')
            if category not in CATEGORIES or not identifier or not contribution.get('source_id'):
                raise DomainError('Political category, evidence identity and citation are required')
            identity = (category, identifier)
            if identity in seen:
                if seen[identity] != contribution:
                    raise DomainError('Conflicting political evidence identity', 3)
                continue
            seen[identity] = contribution
            code = None
            if contribution.get('permission') != 'REVIEWED':
                code = 'CONTRIBUTOR_PERMISSION_UNVERIFIED'
            elif category == 'CORPORATE_PAC' and contribution.get('relationship_verified') is not True:
                code = 'ISSUER_PAC_RELATIONSHIP_UNVERIFIED'
            elif category != 'CORPORATE_PAC' and contribution.get('identity_verified') is not True:
                code = 'CONTRIBUTOR_IDENTITY_UNVERIFIED'
            if code:
                excluded += 1
                issues.append(_issue(code, 'Contribution excluded; reviewed source linkage is required',
                                     issuer_id, identifier))
                continue
            amount = _decimal(contribution['amount'])
            totals[category] = totals.get(category, Decimal(0)) + amount
    return {key: _text(value) for key, value in sorted(totals.items())}, issues, excluded


def summarize(batch):
    """Summarize already validated evidence projections; never accept agent JSON."""
    _date(batch['as_of'])
    if batch.get('data_environment') not in {'REAL', 'SYNTHETIC'}:
        raise DomainError('Research summary environment is unknown', 3)
    if batch.get('window_start'):
        _date(batch['window_start'])
    if batch.get('window_end'):
        if _date(batch['window_end']) > _date(batch['as_of']):
            raise DomainError('Research window extends beyond cutoff')
    issuers = batch['issuers']
    issuer_ids = [row['issuer_id'] for row in issuers]
    if len(issuer_ids) != len(set(issuer_ids)):
        raise DomainError('Research issuer identities must be unique')
    grouped = {}
    for observation in batch.get('research', []):
        if observation['issuer_id'] not in issuer_ids:
            raise DomainError('Research evidence issuer is outside frozen universe', 3)
        if observation['status'] not in STATUSES:
            raise DomainError('Invalid company research coverage status')
        environment = observation.get('data_environment', batch['data_environment'])
        if environment != batch['data_environment'] and not (
                environment is None and observation['status'] == 'REVIEW_REQUIRED'):
            raise DomainError('Mixed research environments cannot share a report', 3)
        grouped.setdefault(observation['issuer_id'], []).append(observation)
    companies, issues = [], copy.deepcopy(batch.get('issues', []))
    required_skills = sorted(batch.get('required_skills', []))
    specialty_coverage = {name: {'requested_issuers': len(issuers), 'researched_issuers': 0,
                                'researched_weight': Decimal(0), 'complete': True}
                          for name in required_skills}
    researched_weight, selected_weight = Decimal(0), Decimal(0)
    excluded = researched = 0
    with localcontext() as context:
        context.prec = max(80, sum(len(row['exposure_weight']) for row in issuers))
        for issuer in issuers:
            weight = _decimal(issuer['exposure_weight'])
            if not 0 <= weight <= 1:
                raise DomainError('Research exposure weight must be between zero and one')
            selected_weight += weight
            evidence = grouped.get(issuer['issuer_id'], [])
            present = [row for row in evidence if row['status'] != 'NOT_RESEARCHED']
            current = [row for row in present if row.get('current_coverage', True)]
            status = 'NOT_RESEARCHED'
            if present:
                if current:
                    researched += 1
                    researched_weight += weight
                status = ('REVIEW_REQUIRED' if any(row['status'] == 'REVIEW_REQUIRED' for row in present)
                          else 'PARTIAL' if any(row['status'] == 'PARTIAL' for row in present)
                          else 'AVAILABLE')
            specialty_statuses = {}
            for name in required_skills:
                observations = [row for row in present if row.get('skill_name') == name]
                specialty_statuses[name] = ('NOT_RESEARCHED' if not observations
                    else 'REVIEW_REQUIRED' if any(row['status'] == 'REVIEW_REQUIRED' for row in observations)
                    else 'PARTIAL' if any(row['status'] == 'PARTIAL' for row in observations)
                    else 'AVAILABLE')
                if any(row.get('current_coverage', True) for row in observations):
                    specialty_coverage[name]['researched_issuers'] += 1
                    specialty_coverage[name]['researched_weight'] += weight
                specialty_coverage[name]['complete'] &= bool(observations) and all(
                    row['status'] == 'AVAILABLE' and row.get('current_coverage', True) for row in observations)
            if status == 'AVAILABLE' and any(value != 'AVAILABLE' for value in specialty_statuses.values()):
                status = 'PARTIAL'
            incomplete = [name for name, value in specialty_statuses.items() if value != 'AVAILABLE']
            if incomplete:
                issues.append(_issue('RESEARCH_TASKS_INCOMPLETE',
                    'Requested specialty research remains missing, partial or requires review',
                    issuer['issuer_id'], *incomplete))
            totals, political_issues, count = _political(evidence, issuer['issuer_id'])
            excluded += count
            issues.extend(political_issues)
            if political_issues and status != 'NOT_RESEARCHED':
                status = 'REVIEW_REQUIRED'
            companies.append(dict(copy.deepcopy(issuer), status=status,
                events=_events(evidence, batch.get('window_start')), political_totals=totals,
                run_hashes=list(dict.fromkeys(row['run_hash'] for row in present)),
                run_ids=list(dict.fromkeys(row['run_id'] for row in present)),
                specialties=[copy.deepcopy(row['specialty']) for row in present if row.get('specialty')],
                specialty_statuses=specialty_statuses))
        if selected_weight > 1:
            raise DomainError('Selected issuer exposure exceeds household denominator', 3)
    coverage = dict(copy.deepcopy(batch.get('coverage', {})), requested_issuers=len(issuers),
                    requested_top=batch.get('requested_top', len(issuers)),
                    researched_issuers=researched, researched_weight=_text(researched_weight),
                    selected_weight=_text(selected_weight), excluded_contributions=excluded,
                    not_researched_issuers=len(issuers) - researched)
    coverage['specialties'] = {name: dict(values, researched_weight=_text(values['researched_weight']),
                                          complete=bool(issuers) and values['complete'])
                               for name, values in specialty_coverage.items()}
    complete = bool(issuers) and researched == len(issuers) and all(
        row['status'] == 'AVAILABLE' for row in companies)
    coverage['selected_research_complete'] = complete
    coverage['whole_portfolio_research_complete'] = bool(complete and selected_weight == 1 and
        all(_decimal(coverage.get(key, '0')) == 0 for key in (
            'unknown_exposure_value', 'stale_exposure_value', 'unresolved_issuer_value')))
    return {'status': 'AVAILABLE' if complete and not issues else 'PARTIAL',
            'as_of': batch['as_of'], 'window_start': batch.get('window_start'),
            'window_end': batch.get('window_end'), 'data_environment': batch['data_environment'],
            'manifest_ids': [batch['manifest_id']] if batch.get('manifest_id') else [],
            'coverage': coverage, 'companies': companies, 'issues': issues,
            'assumptions': {'scope': 'Cited factual research; source truth requires human review'}}


def _snapshot(ledger, identifier):
    row = ledger.connection.execute('SELECT manifest_json FROM data_snapshots WHERE id=?',
                                    (identifier,)).fetchone()
    if row is None:
        raise DomainError('Frozen research manifest does not exist')
    return json.loads(row[0])


def _universe(manifest):
    if 'issuers' in manifest:
        return copy.deepcopy(manifest)
    metadata = manifest.get('metadata', {})
    for key in ('universe', 'research_universe'):
        if isinstance(metadata.get(key), dict):
            return copy.deepcopy(metadata[key])
    if 'issuers' in metadata:
        return copy.deepcopy(metadata)
    raise DomainError('Pinned manifest does not contain an issuer research universe')


def plan(ledger, universe_manifest_id, *, window_start=None, window_end=None):
    """Persist an immutable deterministic research queue, without financial writes."""
    from invest.analytics_store import snapshot, verify_snapshot

    source = _snapshot(ledger, universe_manifest_id)
    verified = verify_snapshot(ledger, source)
    if verified['status'] != 'AVAILABLE':
        return dict(verified, committed=False, queue=[])
    universe = _universe(source)
    as_of = universe['as_of']
    window_end = window_end or as_of
    window_start = window_start or (_date(window_end) - timedelta(days=30)).isoformat()
    if not _date(window_start) <= _date(window_end) <= _date(as_of):
        raise DomainError('Research window chronology is inconsistent')
    empty = summarize(dict(universe, research=[], window_start=window_start, window_end=window_end))
    skills = {name: {'skill_version': values.get('skill_version', SKILL_VERSION),
                     'schema_version': values['schema_version']}
              for name, values in SUPPORTED_SKILLS.items()
              if name in {'investobot-news', 'investobot-political-contributions',
                          'investobot-earnings', 'investobot-competitive',
                          'investobot-management-insiders'}}
    queue = [dict(copy.deepcopy(issuer), status='NOT_RESEARCHED',
                  tasks=[dict(skill_name=name, **identity, status='NOT_RESEARCHED')
                         for name, identity in sorted(skills.items())])
             for issuer in universe['issuers']]
    pinned = {'universe_manifest_id': universe_manifest_id,
              'universe_manifest_hash': _hash(source), 'universe': universe,
              'as_of': as_of, 'window_start': window_start, 'window_end': window_end,
              'data_environment': universe['data_environment'], 'queue': queue,
              'skills': skills, 'coverage': empty['coverage'], 'issues': empty['issues']}
    identifier = 'research-plan-' + _hash(pinned)
    accepted = snapshot(ledger, {'id': identifier, 'purpose': 'RESEARCH_UNIVERSE',
        'as_of': as_of, 'data_environment': universe['data_environment'], 'artifacts': [],
        'metadata': {'research_plan': pinned}}, confirm=True)
    if accepted['status'] != 'AVAILABLE':
        return dict(accepted, id=identifier, queue=queue)
    return dict(pinned, id=identifier, status='PARTIAL', committed=accepted['committed'])


def _matches(issuer, package, envelope):
    if envelope is not None:
        return envelope['issuer_id'] == issuer['issuer_id']
    company = package.get('company') or package.get('subject') or package.get('fund')
    if not company:
        return False
    identity = issuer.get('identity', {})
    for field in ('cik', 'security_id'):
        observed = company.get(field)
        expected = identity.get(field) or issuer.get(field)
        if observed and expected and observed != expected:
            return False
    if any(company.get(field) and company.get(field) == (identity.get(field) or issuer.get(field))
           for field in ('cik', 'security_id')):
        return True
    # Sourced CIK issuer keys can be compared without inventing a canonical ID.
    if company.get('cik') and issuer['issuer_id'] == 'CIK:' + company['cik']:
        return True
    # No ticker-only linkage. A sourced reviewed identity can supply both fields.
    ticker = identity.get('ticker') or issuer.get('ticker')
    name = identity.get('name') or issuer.get('name')
    return bool(ticker and name and company.get('ticker') == ticker and
                ' '.join(company.get('name', '').split()).casefold() ==
                ' '.join(name.split()).casefold() and not company.get('cik') and
                not company.get('security_id'))


def _news_events(ledger, records):
    """Carry older active observations explicitly; cited terminal records tombstone."""
    from invest.news_queries import summary

    events = {}
    baseline = records[0]['run_id']
    for record in records:
        package = summary(ledger, record['run_id'])
        sources = {source['source_id']: source for source in package['sources']}
        for original in package['events']:
            key = original['event_key']
            if key in events:
                continue
            event = copy.deepcopy(original)
            event['sources'] = [sources[source_id] for source_id in event['source_ids']]
            event['observed_run_id'] = record['run_id']
            event['observed_as_of'] = record['researched_as_of']
            event['published_dates'] = sorted({source['published_at']
                for source in event['sources'] if source.get('published_at')})
            event['observation_status'] = 'OBSERVED_IN_BASELINE' if record['run_id'] == baseline else 'NOT_REOBSERVED'
            if record['run_id'] != baseline:
                if event['event_status'] in {'RESOLVED', 'RETRACTED'}:
                    # A terminal record prevents an older active observation from
                    # being revived, even if absent in the newest package.
                    events[key] = None
                    continue
                event['recorded_event_status'] = event['event_status']
                event['event_status'] = 'NOT_REOBSERVED'
            events[key] = event
    return [event for key, event in sorted(events.items()) if event is not None]


def _candidate_rows(ledger, issuer, pinned):
    """Select compact issuer metadata before accessing any evidence package."""
    identity = issuer.get('identity', {})
    cik = identity.get('cik') or (issuer['issuer_id'][4:] if issuer['issuer_id'].startswith('CIK:') else None)
    security_id = identity.get('security_id') or issuer.get('security_id')
    ticker = identity.get('ticker') or issuer.get('ticker')
    name = identity.get('name') or issuer.get('name')
    skills = sorted(pinned['skills'])
    placeholders = ','.join('?' for _ in skills)
    return ledger.connection.execute('''WITH compact AS (
        SELECT r.id,r.skill_name,r.researched_as_of,r.coverage_status,r.imported_at,
            r.cik,r.security_id,r.ticker,r.company_name,a.metadata_json
        FROM research_runs r LEFT JOIN research_artifacts a ON a.run_id=r.id AND a.id='provenance'
        UNION ALL SELECT p.id,'investobot-political-contributions',p.researched_as_of,
            p.coverage_status,p.imported_at,NULL,p.security_id,p.ticker,p.company_name,NULL
        FROM research_political_runs p WHERE NOT EXISTS (SELECT 1 FROM research_runs r WHERE r.id=p.id))
        SELECT r.id,r.skill_name,r.researched_as_of,r.coverage_status FROM compact r
        WHERE r.researched_as_of<=? AND r.skill_name IN (''' + placeholders + ''') AND (
          (r.metadata_json IS NOT NULL AND json_extract(r.metadata_json,'$.issuer_id')=?) OR
          (r.metadata_json IS NULL AND (r.cik=? OR r.security_id=? OR
           (r.cik IS NULL AND r.security_id IS NULL AND r.ticker=?
            AND lower(trim(r.company_name))=lower(trim(?))))))
        ORDER BY r.researched_as_of DESC,r.imported_at DESC,r.id LIMIT 1001''',
        (pinned['as_of'], *skills, issuer['issuer_id'], cik, security_id, ticker, name)).fetchall()


def _covers_window(evidence, pinned):
    scope = evidence['package'].get('scope', {})
    start = scope.get('window_start') or scope.get('period_start')
    end = scope.get('window_end') or scope.get('period_end')
    if start is not None and end is not None:
        overlaps = _date(start) <= _date(pinned['window_end']) and _date(end) >= _date(pinned['window_start'])
        complete = _date(start) <= _date(pinned['window_start']) and _date(end) >= _date(pinned['window_end'])
        return overlaps, complete
    # Point-in-time specialties retain their exact reporting-period semantics.
    # Recent research is not rewritten into an invented interval/quarter.
    current = _date(pinned['window_start']) <= _date(evidence['researched_as_of']) <= _date(pinned['window_end'])
    return current, current


def report(ledger, plan_id):
    """Read accepted source-backed evidence against a frozen queue; never browse."""
    from invest.analytics_store import verify_snapshot
    from invest.research_storage import show

    manifest = _snapshot(ledger, plan_id)
    pinned = manifest.get('metadata', {}).get('research_plan')
    if not isinstance(pinned, dict):
        raise DomainError('Selected manifest is not a frozen research plan')
    source = _snapshot(ledger, pinned['universe_manifest_id'])
    if _hash(source) != pinned['universe_manifest_hash']:
        raise DomainError('Frozen universe content no longer matches research plan', 3)
    verified = verify_snapshot(ledger, source)
    if verified['status'] != 'AVAILABLE':
        return dict(verified, id=plan_id, companies=[])
    universe = pinned['universe']
    cutoff = pinned['as_of']
    projections, issues = [], copy.deepcopy(universe.get('issues', []))
    for issuer in universe['issuers']:
        rows = _candidate_rows(ledger, issuer, pinned)
        truncated = len(rows) > 1000
        if truncated:
            issues.append(_issue('RESEARCH_HISTORY_TRUNCATED',
                'Selected issuer history exceeds the bounded report; older context requires explicit review',
                issuer['issuer_id']))
        candidates = []
        for run_id, skill_name, researched_as_of, coverage_status in rows[:1000]:
            evidence = show(ledger, run_id)
            if skill_name == 'investobot-political-contributions' and not evidence.get('envelope'):
                # Original native packages pin their accepted skill identity.
                evidence['skill_version'] = evidence['package'].get('skill_version')
                evidence['schema_version'] = evidence['package'].get('schema_version')
            candidates.append(dict(evidence, run_id=run_id, skill_name=skill_name,
                                   researched_as_of=researched_as_of, coverage_status=coverage_status))
        families = {}
        for evidence in candidates:
            if not _matches(issuer, evidence['package'], evidence.get('envelope')):
                continue
            envelope = evidence.get('envelope')
            if envelope and envelope['data_environment'] != universe['data_environment']:
                issues.append(_issue('MIXED_DATA_ENVIRONMENT', 'Research run excluded from incompatible universe',
                                     issuer['issuer_id'], evidence['run_id']))
                continue
            package = evidence['package']
            if any(source.get(key) and _date(str(source[key])[:10]) > _date(cutoff)
                   for source in package.get('sources', [])
                   for key in ('published_at', 'accessed_at', 'filed_at')):
                issues.append(_issue('FUTURE_RESEARCH_SOURCE',
                    'Research source was not known by frozen cutoff', issuer['issuer_id'], evidence['run_id']))
                continue
            trusted = pinned['skills'].get(evidence['skill_name'])
            if trusted is None or evidence['skill_version'] != trusted['skill_version']:
                issues.append(_issue('RESEARCH_SKILL_VERSION_MISMATCH',
                    'Run does not match frozen research skill identity', issuer['issuer_id'], evidence['run_id']))
                if envelope is not None:
                    continue
            families.setdefault(evidence['skill_name'], []).append(evidence)
        for skill_name, records in families.items():
            evidence = records[0]
            status = 'AVAILABLE' if evidence['coverage_status'] == 'COMPLETE_WITHIN_DECLARED_SCOPE' else 'PARTIAL'
            current_coverage, complete_window = _covers_window(evidence, pinned)
            if not complete_window:
                status = 'PARTIAL' if current_coverage else 'REVIEW_REQUIRED'
                issues.append(_issue('RESEARCH_WINDOW_NOT_COVERED',
                    'Accepted evidence does not cover the requested research window; retained as historical context',
                    issuer['issuer_id'], evidence['run_id']))
            if truncated:
                status = 'REVIEW_REQUIRED'
            if evidence.get('envelope') is None:
                status = 'REVIEW_REQUIRED'
                issues.append(_issue('RESEARCH_ENVIRONMENT_UNVERIFIED',
                    'Legacy specialty evidence has no accepted environment provenance',
                    issuer['issuer_id'], evidence['run_id']))
            projection = {'issuer_id': issuer['issuer_id'], 'status': status,
                'run_id': evidence['run_id'], 'run_hash': evidence['run_id'],
                'current_coverage': current_coverage,
                'data_environment': evidence.get('envelope', {}).get('data_environment'),
                'events': [], 'political': [],
                'skill_name': skill_name, 'skill_version': evidence['skill_version']}
            if skill_name == 'investobot-news':
                projection['events'] = _news_events(ledger, records)
                if not current_coverage:
                    for event in projection['events']:
                        event['observation_status'] = 'NOT_REOBSERVED'
            elif skill_name == 'investobot-political-contributions':
                package = evidence['package']
                for contribution in package.get('contributions', []):
                    if not contribution['countable'] or not current_coverage:
                        continue
                    projection['political'].append({'id': contribution['id'],
                        'category': contribution.get('contributor_category') or 'EXECUTIVE_PERSONAL',
                        'amount': contribution['amount_usd'],
                        'relationship_verified': bool(contribution.get('corporate_pac_identity_evidence', {}).get('reviewed')),
                        'permission': 'REVIEWED' if package['scope']['rights_status'] == 'APPROVED' else 'UNKNOWN',
                        'identity_verified': contribution['identity_status'] == 'VERIFIED',
                        'source_id': contribution['source_ids'][0],
                        'source_ids': contribution['source_ids']})
            query_modules = {'investobot-earnings': 'earnings_queries',
                             'investobot-competitive': 'competitive_queries',
                             'investobot-management-insiders': 'insider_queries',
                             'investobot-political-contributions': 'political_queries',
                             'investobot-news': 'news_queries'}
            query = importlib.import_module('invest.' + query_modules[skill_name])
            projection['specialty'] = {'skill_name': skill_name,
                'skill_version': evidence['skill_version'], 'run_id': evidence['run_id'],
                'run_hash': evidence['run_id'], 'status': status,
                'current_coverage': current_coverage,
                'data_environment': evidence.get('envelope', {}).get('data_environment'),
                'summary': query.summary(ledger, evidence['run_id'])}
            projections.append(projection)
    result = summarize(dict(universe, manifest_id=pinned['universe_manifest_id'],
                            window_start=pinned['window_start'], window_end=pinned['window_end'],
                            research=projections, issues=issues, required_skills=sorted(pinned['skills'])))
    result.update(id=plan_id, universe_manifest_id=pinned['universe_manifest_id'],
                  skill_versions=pinned['skills'], mutation_scope='none')
    return result
