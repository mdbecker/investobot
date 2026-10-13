const $ = id => document.getElementById(id);
const pretty = value => JSON.stringify(value, null, 2);
const text = value => value === null || value === undefined ? 'Unknown' : String(value);
const selectedBacktests = new Set();
let state = {securities: [], accounts: []};
const securityLabel = id => state.securities.find(row => row.id === id)?.ticker || id;

function el(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = text(value);
  if (className) node.className = className;
  return node;
}
async function api(route) {
  const response = await fetch(`/api/${route}`);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Stored data is unavailable');
  return result;
}
async function run(action) {
  try { await action(); }
  catch (error) { $('notice').textContent = error.message; $('notice').hidden = false; }
}
function table(container, headers, rows) {
  if (!rows?.length) { container.append(el('p', 'No available rows.', 'muted')); return; }
  const scroll = el('div', undefined, 'table-scroll');
  const grid = el('table'); const head = el('tr');
  headers.forEach(title => head.append(el('th', title))); grid.append(head);
  rows.forEach(values => { const row = el('tr'); values.forEach(value => row.append(el('td', value))); grid.append(row); });
  scroll.append(grid); container.append(scroll);
}
function details(container, title, value) {
  const node = el('details'); node.append(el('summary', title), el('pre', pretty(value))); container.append(node);
}
function warnings(container, values) {
  if (values?.length) container.append(el('p', values.map(value => typeof value === 'string' ? value : pretty(value)).join(' · '), 'warnings'));
}
function button(label, action) {
  const node = el('button', label, 'secondary'); node.type = 'button';
  node.addEventListener('click', () => run(action)); return node;
}
function badge(status) { return el('span', status || 'Unknown status', `badge ${status === 'STALE' ? 'status-stale' : ''}`); }
function drift(container, rows) {
  table(container, ['Security', 'Current value', 'Target value', 'Dollar drift', 'Weight drift'],
    (rows || []).map(row => [securityLabel(row.security_id), row.current_value, row.target_value, row.difference_value, row.difference_weight]));
}
function savedRow(container, label, subtitle, status, action) {
  const row = el('article', undefined, 'saved-row'); const caption = el('div');
  caption.append(el('strong', label), el('small', subtitle));
  row.append(caption, badge(status), button('Inspect saved result', action)); container.append(row); return row;
}
async function refreshOverview() {
  const result = await api('overview'); state = result.state;
  $('total').textContent = text(result.summary.total_value);
  $('cash').textContent = text(result.summary.cash);
  $('gain').textContent = text(result.summary.unrealized_gain_loss_known_basis);
  $('empty').hidden = state.accounts.length > 0;
  warnings($('overview-warnings'), result.summary.warnings); $('overview-warnings').hidden = !result.summary.warnings?.length;
  for (const account of state.accounts) {
    const card = el('article', undefined, 'account'); card.append(el('h3', account.name || account.id),
      el('p', `${account.tax_status} · ${account.currency} · ${account.data_environment}`, 'muted'));
    table(card, ['Security', 'Quantity', 'Accepted value', 'Accepted price', 'Basis'], state.positions.filter(row => row.account_id === account.id)
      .map(row => [row.security, row.quantity, row.market_value, row.price, row.cost_basis]));
    const cash = state.cash_balances.find(row => row.account_id === account.id);
    card.append(el('p', `Accepted cash: ${text(cash?.amount)}`, 'muted')); $('accounts').append(card);
  }
  table($('freshness'), ['Account', 'Source date', 'Import date', 'Positions complete', 'Lots complete', 'Cash known'],
    result.data_freshness.map(row => [row.account_id, row.source_timestamp, row.imported_at, row.positions_complete, row.lots_complete, row.cash_known]));
  table($('exposure'), ['Exposure', 'Accepted value', 'Portfolio %'], result.exposure.exposures.map(row => [row.ticker || row.identifier, row.total_value, row.percentage]));
  $('exposure').append(el('p', result.exposure.unknown_exposure_percentage === null
    ? 'Exposure percentages unavailable: accepted valuation or cash coverage is incomplete.'
    : `Unknown exposure: ${text(result.exposure.unknown_exposure_percentage)}%`, 'muted'));
  warnings($('exposure'), result.exposure.warnings); details($('exposure'), 'Stored source evidence', result.exposure.provenance);
  if (result.exposure.issues?.length) details($('exposure'), 'Exposure coverage issues', result.exposure.issues);
  warnings($('tax-lots'), result.tax_lots.warnings); details($('tax-lots'), 'Accepted tax-lot facts', result.tax_lots);
  $('active-target').append(el('p', result.active_target?.name || 'No active target.', 'muted'));
  if (result.target_diff) {
    drift($('active-target'), result.target_diff.allocations);
    warnings($('active-target'), result.target_diff.warnings);
  }
}
async function loadTarget(id) {
  const target = await api(`targets/${encodeURIComponent(id)}`);
  const container = $('target-detail'); container.replaceChildren(el('h3', target.name), badge(target.status));
  const result = await api(`targets/${encodeURIComponent(id)}/diff?version=${target.version}`);
  drift(container, result.allocations); warnings(container, result.warnings);
  details(container, 'Saved target versions and assumptions', target); container.hidden = false;
}
async function refreshTargets() {
  const {targets} = await api('targets');
  for (const target of targets) savedRow($('target-list'), target.name, `Version ${target.version}`, target.status, () => loadTarget(target.id));
  if (!targets.length) $('target-list').append(el('p', 'No targets saved.', 'muted'));
}
async function loadPlan(id) {
  const plan = await api(`plans/${encodeURIComponent(id)}`); const container = $('plan-detail');
  container.replaceChildren(el('h3', plan.name), badge(plan.status));
  if (plan.status === 'STALE') container.append(el('p', 'Accepted source facts changed. This saved plan needs renewed human review.', 'warnings status-stale'));
  warnings(container, plan.warnings);
  table(container, ['Account', 'Action', 'Security', 'Quantity', 'Hypothetical price', 'Selected lots'],
    (plan.proposed_actions || []).map(row => [row.account_id, row.type, securityLabel(row.security), row.quantity, row.price,
      row.lot_allocations ? pretty(row.lot_allocations) : 'Not applicable or unresolved']));
  table(container, ['Account', 'Cash before', 'Cash after'], Object.keys(plan.cash_before || {}).map(account => [account, plan.cash_before[account], plan.cash_after?.[account]]));
  drift(container, plan.remaining_target_drift); details(container, 'Saved tax analysis and review limitations', plan.tax_analysis);
  details(container, 'Complete immutable plan and source evidence', plan);
  for (const format of ['markdown', 'json']) {
    const link = el('a', `Download ${format} report`, 'file-label'); link.href = `/api/plans/${encodeURIComponent(id)}/report?format=${format}`; link.setAttribute('download', ''); container.append(link);
  }
  container.hidden = false;
}
async function refreshPlans() {
  const {plans} = await api('plans');
  for (const plan of plans) savedRow($('plan-list'), plan.name, `${plan.created_at} · ${plan.trade_count} proposed trades`, plan.status, () => loadPlan(plan.id));
  if (!plans.length) $('plan-list').append(el('p', 'No plans saved.', 'muted'));
}
async function refreshBacktests() {
  const {runs} = await api('backtests');
  for (const result of runs) {
    const row = savedRow($('backtest-list'), result.name || result.id, `${result.start} → ${result.end}`, result.status, async () => {
      const saved = await api(`backtests/${encodeURIComponent(result.id)}`);
      $('backtest-detail').replaceChildren(el('h3', 'Saved historical result'), el('pre', pretty(saved))); $('backtest-detail').hidden = false;
    });
    const check = el('input'); check.type = 'checkbox'; check.setAttribute('aria-label', `Compare saved backtest ${result.id}`);
    check.addEventListener('change', () => check.checked ? selectedBacktests.add(result.id) : selectedBacktests.delete(result.id)); row.prepend(check);
  }
  if (!runs.length) $('backtest-list').append(el('p', 'No historical backtests saved.', 'muted'));
}
$('backtest-compare').addEventListener('click', () => run(async () => {
  if (selectedBacktests.size < 2) throw new Error('Select at least two saved backtests.');
  const query = new URLSearchParams(); selectedBacktests.forEach(id => query.append('run_id', id));
  const result = await api(`backtests/compare?${query}`); const container = $('backtest-comparison');
  container.replaceChildren(el('h3', 'Saved backtest comparison'), badge(result.status)); warnings(container, result.issues);
  table(container, ['Run', 'Period', 'Return', 'Final value', 'Drawdown', 'Turnover'], result.runs.map(row => [row.id, `${row.start} → ${row.end}`, row.total_return, row.final_value, row.max_drawdown, row.turnover]));
  details(container, 'Persisted assumptions and complete comparison', result); container.hidden = false;
}));
$('review-date').value = new Date().toISOString().slice(0, 10);
$('review-check').addEventListener('click', () => run(async () => {
  const result = await api(`check?as_of=${encodeURIComponent($('review-date').value)}`);
  $('preflight-result').replaceChildren(el('pre', pretty(result)));
}));
$('performance-read').addEventListener('click', () => run(async () => {
  const query = new URLSearchParams();
  if ($('performance-from').value) query.set('from', $('performance-from').value);
  if ($('performance-to').value) query.set('to', $('performance-to').value);
  const result = await api(`performance?${query}`); $('performance-result').replaceChildren(el('pre', pretty(result)));
}));
function navigation() {
  const selected = location.hash || '#overview';
  document.querySelectorAll('a.nav').forEach(link => { const active = link.getAttribute('href') === selected; link.classList.toggle('active', active); if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
}
window.addEventListener('hashchange', navigation); navigation();
for (const load of [refreshOverview, refreshTargets, refreshPlans, refreshBacktests]) run(load);
