'use strict';
const $ = id => document.getElementById(id);
let snapshot = null;
let snapshotReconciliation = null;
let activityPreview = null;
const pretty = value => JSON.stringify(value, null, 2);
let displayCurrency = 'USD';
const money = value => value === undefined || value === null ? 'Unknown' : new Intl.NumberFormat('en-US', {style:'currency', currency:displayCurrency}).format(String(value));
function notice(message, error=false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = false; }
async function api(path, body) {
  const response = await fetch('/api/' + path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed');
  return value;
}
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
async function refresh() {
  const overview = await api('overview');
  const {summary, state} = overview;
  householdState = state;
  displayCurrency = summary.currency || 'USD';
  $('total').textContent = money(summary.total_value); $('cash').textContent = money(summary.cash);
  $('gain').textContent = money(summary.unrealized_gain_loss_known_basis); $('summary-json').textContent = pretty(summary);
  $('empty').hidden = state.accounts.length > 0; $('accounts').replaceChildren();
  for (const account of state.accounts) {
    const card = el('article', undefined, 'account'); const head = el('div', undefined, 'account-head');
    const caption = el('div'); caption.append(el('h3', account.name), el('small', `${account.institution} · ${account.tax_status.replaceAll('_',' ')}`));
    head.append(caption, el('strong', money(summary.by_account[account.id]))); card.append(head);
    const table = el('table'); const title = el('tr'); ['Security','Quantity','Asset type','Market value'].forEach(x=>title.append(el('th',x)));
    const thead = el('thead'); thead.append(title); table.append(thead); const body = el('tbody');
    for (const position of state.positions.filter(p=>p.account_id===account.id)) {
      const row = el('tr'); [position.security, position.quantity, position.asset_type, money(position.market_value)].forEach(x=>row.append(el('td',x))); body.append(row);
    }
    const cash = state.cash_balances.find(c=>c.account_id===account.id);
    if (cash) { const row=el('tr'); ['Cash','—','CASH',money(cash.amount)].forEach(x=>row.append(el('td',x))); body.append(row); }
    table.append(body); card.append(table); $('accounts').append(card);
  }
  $('warnings').hidden = !summary.warnings.length; $('warnings').textContent = summary.warnings.join(' · ');
  $('active-target').textContent = overview.active_target ? `${overview.active_target.name} · version ${overview.active_target.version}` : 'No active target. Save and activate a candidate in Targets.';
  $('active-drift').replaceChildren();
  if (overview.target_diff) allocationTable($('active-drift'), overview.target_diff.allocations);
  const exposure = overview.exposure || {};
  $('exposure-summary').textContent = exposure.unknown_exposure_value === undefined ? 'Exposure data unavailable. Review the warnings and analysis tools.' : `Unresolved exposure: ${money(exposure.unknown_exposure_value)} · ${exposure.unknown_exposure_percentage}%`;
  $('concentrations').replaceChildren();
  tableInto($('concentrations'), ['Security','Household exposure','Identifier confidence'], (exposure.exposures || []).slice(0, 8).map(row => [row.ticker || row.identity || row.name, `${row.percentage}%`, row.identifier_confidence]));
  warningInto('exposure-warnings', exposure.warnings || []);
  $('freshness').replaceChildren();
  tableInto($('freshness'), ['Account','Source date','Imported','Positions complete','Lots complete','Cash known'], (overview.data_freshness || []).map(row => [row.account_id, row.source_timestamp || 'Unknown', row.imported_at || 'Unknown', row.positions_complete ? 'Yes' : 'No', row.lots_complete ? 'Yes' : 'No', row.cash_known ? 'Yes' : 'No']));
  $('lot-json').textContent = pretty(overview.tax_lots || {});
  warningInto('lot-warnings', overview.tax_lots?.warnings || []);
  $('security-catalogue').replaceChildren();
  tableInto($('security-catalogue'), ['Security','Canonical ID','Asset type'], state.securities.map(row => [row.ticker, row.id, row.asset_type]));
  $('target-drift').replaceChildren();
  $('plan-comparison').hidden = true;
  await Promise.all([refreshTargets(), refreshPlans(), refreshPrompts()]);
}
function updateSnapshotAcceptance() {
  const overrideChecked = $('older-confirm').checked;
  const overrideReady = (!snapshotReconciliation?.override_required || overrideChecked) && (!overrideChecked || $('older-justification').value.trim().length > 0);
  $('apply').disabled = !snapshot || !snapshotReconciliation || !$('accept-confirm').checked || !overrideReady;
}
function clearPreview() { snapshot = null; snapshotReconciliation = null; $('preview-area').hidden = true; $('reconcile-area').hidden = true; $('accept-confirm').checked = false; $('older-confirm').checked = false; $('older-justification').value = ''; $('apply').disabled = true; }
async function run(action) { try { await action(); } catch(error) { notice(error.message, true); } }
$('refresh').addEventListener('click',()=>run(refresh));
$('import-form').addEventListener('input',clearPreview);
$('html-file').addEventListener('change',()=>run(async()=>{
  const file = $('html-file').files[0]; if (!file) return;
  if (file.size > 1_900_000) throw new Error('HTML file is too large. Use a page smaller than 1.9 MB.');
  $('html-input').value = await file.text(); clearPreview();
}));
$('import-form').addEventListener('submit',event=>{ event.preventDefault(); run(async()=>{
  clearPreview(); const body = Object.fromEntries(new FormData(event.target));
  body.positions_complete = event.target.elements.positions_complete.checked;
  body.lots_complete = event.target.elements.lots_complete.checked;
  snapshot = await api('import',body); $('preview-json').textContent = pretty(snapshot); $('preview-area').hidden=false;
  $('html-input').value=''; $('html-file').value=''; notice('Preview ready. The ledger has not changed. Review the values, then compare with your ledger.');
}); });
$('reconcile').addEventListener('click',()=>run(async()=>{
  if (!snapshot) throw new Error('Preview an account page first.');
  const result = await api('reconcile',{snapshot}); $('reconcile-json').textContent=pretty(result); $('reconcile-area').hidden=false;
  snapshotReconciliation = result;
  $('accept-confirm').checked = false;
  $('older-confirm').checked = false;
  $('older-justification').value = '';
  let warnings = $('snapshot-review-warnings');
  if (!warnings) { warnings = el('div', undefined, 'warnings'); warnings.id = 'snapshot-review-warnings'; $('reconcile-json').before(warnings); }
  const messages = [...(result.warnings || [])];
  for (const review of result.classification_reviews || []) {
    messages.push(`${review.ticker || review.security_id} (${review.security_id}): accepted classification ${review.canonical_type}; imported page suggests ${review.observed_type}. Holdings acceptance preserves the accepted type. Review a verified source, then preview invest security classify ${review.security_id} --asset-type ${review.observed_type} --source "Verified source" and use --confirm only after review.`);
  }
  if (result.account_metadata_discrepancies?.length) messages.push('Incoming account metadata differs. Snapshot acceptance preserves account configuration. Use invest account update for a reviewed correction.');
  if (result.source_date_status === 'UNKNOWN_SOURCE_DATE') messages.push('Source date is unknown. Import time does not establish freshness.');
  if (result.source_date_status === 'OLDER_THAN_ACCEPTED') messages.push('Source date is older than previously accepted observations.');
  if (result.override_required) messages.push(`Ordinary acceptance is blocked. Latest known source date: ${result.latest_known_source_date || 'Unknown'}. Review and explicitly override with an explanation.`);
  warnings.textContent = messages.join(' · '); warnings.hidden = !messages.length;
  updateSnapshotAcceptance();
}));
for (const id of ['accept-confirm','older-confirm']) $(id).addEventListener('change', updateSnapshotAcceptance);
$('older-justification').addEventListener('input', updateSnapshotAcceptance);
$('apply').addEventListener('click',()=>run(async()=>{
  updateSnapshotAcceptance();
  if ($('apply').disabled) throw new Error('Reconcile and confirm the snapshot; required freshness overrides need an explanation.');
  await api('apply',{snapshot,confirm:true,allow_older:$('older-confirm').checked,justification:$('older-justification').value || null}); clearPreview(); await refresh(); notice('Snapshot accepted. Review saved plans for stale source state.');
}));
function clearActivity() { activityPreview = null; $('activity-confirm').checked=false; $('activity-save').disabled=true; $('activity-result').hidden=true; }
$('activity-input').addEventListener('input',clearActivity);
$('activity-preview').addEventListener('click',()=>run(async()=>{
  clearActivity(); const activity=JSON.parse($('activity-input').value); const result=await api('activity',{activity}); activityPreview=activity;
  $('activity-result').textContent=pretty(result); $('activity-result').hidden=false; notice('Activity preview ready. The ledger has not changed.');
}));
$('activity-confirm').addEventListener('change',()=>{$('activity-save').disabled=!activityPreview || !$('activity-confirm').checked;});
$('activity-save').addEventListener('click',()=>run(async()=>{
  if (!activityPreview || !$('activity-confirm').checked) throw new Error('Preview and confirm this activity first.');
  const result=await api('activity',{activity:activityPreview,confirm:true}); clearActivity(); $('activity-result').textContent=pretty(result); $('activity-result').hidden=false;
  await refresh(); notice('Manually executed activity recorded in your ledger.');
}));
const analysisTemplates = {
  exposure: {},
  tax_lots: {as_of:'2026-10-08'},
  tax_analyze: {account:'your-account-alias',security:'VTI',quantity:'1',price:'100',sale_date:'2026-10-08',method:'FIFO'},
  harvest: {as_of:'2026-10-08'},
  simulate: {actions:[{type:'BUY',account_id:'your-account-alias',security:'VTI',quantity:'1',price:'100',date:'2026-10-08',fee:'0'}]},
  risk: {},
  fund_holdings: {ticker:'VTI'},
  fund_compare: {a:'VTI',b:'ITOT'},
  bond_analyze: {terms:{face_value:'1000',coupon:'0.05',issue_date:'2021-01-15',maturity:'2031-01-15',settlement_date:'2026-10-08',frequency:2,clean_price:'98',day_count:'ACTUAL_ACTUAL_BOND'}}
};
const analysisHints = {
  exposure:'Uses loaded positions. Unresolved fund holdings and classifications remain explicit unknown exposure.',
  tax_lots:'Uses imported basis and local prices. Optional as_of is an ISO date; omitted dates use the server current date.',
  tax_analyze:'Supply a loaded account alias/security and your assumed sale price/date. Methods: FIFO, LIFO, HIFO, SPECIFIC (with lot_ids), MIN_TAX (requires configured rates).',
  harvest:'Examines known taxable losses. Missing basis or prices remain insufficient data.',
  simulate:'Edit hypothetical BUY, SELL or MOVE_CASH actions. Existing security identifiers must resolve; no holdings or cash are persisted.',
  risk:'Historical data requires FMP configuration or explicit synthetic fixture mode. Missing history is disclosed.',
  fund_holdings:'Requires FMP configuration or explicit fixture mode. Data source/as-of metadata identifies synthetic, partial or unavailable data.',
  fund_compare:'Compares complete available holdings and history. Similarity does not determine wash-sale legality.',
  bond_analyze:'Template values are synthetic known terms. Replace them with researched terms; coupon is an annual decimal fraction and clean price is per 100 face value.'
};
function selectAnalysis() {
  const tool=$('analysis-tool').value; $('analysis-input').value=pretty(analysisTemplates[tool]);
  $('analysis-hint').textContent=analysisHints[tool]; $('analysis-result').hidden=true;
}
$('analysis-tool').addEventListener('change',selectAnalysis);
$('analysis-example').addEventListener('click',selectAnalysis);
$('analysis-run').addEventListener('click',()=>run(async()=>{
  const button=$('analysis-run'); button.disabled=true; button.textContent='Calculating…'; $('analysis-result').hidden=true;
  try {
    const tool=$('analysis-tool').value; const input=JSON.parse($('analysis-input').value);
    const result=await api('analyze',{tool,input}); $('analysis-json').textContent=pretty(result);
    $('analysis-title').textContent=$('analysis-tool').selectedOptions[0].textContent;
    $('analysis-metrics').replaceChildren();
    const selected = [
      ['status','Status'],['total_value','Portfolio value'],['unknown_exposure_percentage','Unknown exposure %'],
      ['overlap','Weighted overlap'],['active_share','Active share'],['realized_gain_loss','Realized gain/loss'],
      ['annualized_volatility','Annualized volatility'],['maximum_drawdown','Maximum drawdown'],
      ['short_term_gain_loss','Short-term gain/loss'],['long_term_gain_loss','Long-term gain/loss'],
      ['yield_to_maturity','Yield to maturity'],['modified_duration','Modified duration'],['source','Data source']
    ];
    for(const [key,label] of selected) if(result[key]!==undefined && result[key]!==null) {
      const card=el('div',undefined,'result-metric'); card.append(el('span',label),el('strong',String(result[key]))); $('analysis-metrics').append(card);
    }
    for(const [key,label] of [['lots','Tax lots'],['exposures','Underlying exposures'],['holdings','Fund holdings'],['candidates','Candidates']]) if(Array.isArray(result[key])) {
      const card=el('div',undefined,'result-metric'); card.append(el('span',label),el('strong',String(result[key].length))); $('analysis-metrics').append(card);
    }
    if(result.before && result.after) {const card=el('div',undefined,'result-metric');card.append(el('span','Cash before → after'),el('strong',`${money(result.before.cash)} → ${money(result.after.cash)}`));$('analysis-metrics').append(card);}
    $('analysis-warnings').textContent=(result.warnings||[]).join(' · '); $('analysis-warnings').hidden=!(result.warnings||[]).length;
    $('analysis-result').hidden=false; notice('Analysis complete. Your ledger and provider cache have not changed.');
  } finally {button.disabled=false;button.textContent='Run analysis';}
}));
selectAnalysis();

// Render domain values only. Decimal arithmetic, identity resolution and status
// decisions belong to the same server-side functions used by the CLI.
let householdState = {securities:[], accounts:[]};
let selectedTarget = null;
let selectedPrompt = null;
let selectedPlan = null;
let promptDirty = false;
const selectedPlanIds = new Set();
const securityLabel = id => id === 'CASH' ? 'Cash' : householdState.securities.find(s => s.id === id)?.ticker || id;
function warningInto(id, warnings) {
  $(id).textContent = warnings.map(w => typeof w === 'string' ? w : pretty(w)).join(' · ');
  $(id).hidden = warnings.length === 0;
}
function tableInto(container, headers, rows) {
  if (!rows.length) { container.append(el('p', 'No available rows.', 'muted')); return; }
  const scroll = el('div', undefined, 'table-scroll'); const table = el('table');
  const head = el('thead'); const title = el('tr'); headers.forEach(h => title.append(el('th', h))); head.append(title); table.append(head);
  const body = el('tbody');
  rows.forEach(values => { const row = el('tr'); values.forEach(value => row.append(el('td', value === null || value === undefined ? 'Unknown' : String(value)))); body.append(row); });
  table.append(body); scroll.append(table); container.append(scroll);
}
function allocationTable(container, rows) {
  tableInto(container, ['Security','Current value','Target value','Dollar drift','Current weight (fraction)','Target weight (fraction)'], (rows || []).map(row => [securityLabel(row.security_id), money(row.current_value), money(row.target_value), money(row.difference_value), row.current_weight, row.target_weight]));
}
function button(text, action, secondary=true) {
  const node = el('button', text, secondary ? 'secondary' : undefined);
  node.type = 'button'; node.addEventListener('click', () => run(action)); return node;
}
function statusBadge(status) {
  const node = el('span', status?.replaceAll('_',' ') || 'Unknown status', 'badge');
  if (status === 'STALE') node.classList.add('status-stale');
  else if (status === 'REVIEW_REQUIRED') node.classList.add('status-review');
  return node;
}
function jsonDetails(container, title, value) {
  const details = el('details'); details.append(el('summary', title), el('pre', pretty(value))); container.append(details);
}
function targetInput(target) {
  return Object.fromEntries(['id','name','description','status','target_allocations','planning_constraints'].map(key => [key,target[key]]));
}
async function refreshTargets() {
  const result = await api('targets'); const targets = result.targets || [];
  $('target-list').replaceChildren();
  const prior = $('plan-target').value; $('plan-target').replaceChildren(el('option', 'Choose a saved target'));
  $('plan-target').firstChild.value = '';
  for (const target of targets) {
    const row = el('article', undefined, 'saved-row'); const caption = el('div');
    caption.append(el('strong', target.name), el('small', `Version ${target.version} · ${target.description || 'No description'}`));
    row.append(caption, statusBadge(target.status), button('Inspect & edit', () => loadTarget(target.id)));
    $('target-list').append(row);
    const option = el('option', `${target.name} · v${target.version} · ${target.status}`); option.value = target.id; $('plan-target').append(option);
  }
  if (!targets.length) $('target-list').append(el('p', 'No targets saved. Start with an editable draft below.', 'muted'));
  if (targets.some(t => t.id === prior)) $('plan-target').value = prior;
}
async function loadTarget(id, version) {
  selectedTarget = await api(`targets/${encodeURIComponent(id)}${version ? '?version=' + encodeURIComponent(version) : ''}`);
  const target = selectedTarget;
  $('target-title').textContent = target.name; $('target-status').textContent = `${target.status} · version ${target.version}`;
  $('target-json').textContent = pretty(target); $('target-input').value = pretty(targetInput(target));
  $('target-version').replaceChildren();
  for (const saved of target.versions || []) { const option = el('option', `Version ${saved.version} · ${saved.updated_at}`); option.value = saved.version; $('target-version').append(option); }
  $('target-version').value = target.version; $('target-detail').hidden = false; $('target-drift').replaceChildren();
}
$('target-version').addEventListener('change', () => run(() => loadTarget(selectedTarget.id, $('target-version').value)));
$('target-new').addEventListener('click', () => {
  selectedTarget = null; $('target-detail').hidden = true;
  $('target-input').value = pretty({name:'New draft',description:'Describe your rationale',status:'DRAFT',target_allocations:{CASH:'1'},planning_constraints:{eligible_accounts:[],permitted_securities:{}}});
  $('target-input').focus();
});
$('target-save').addEventListener('click', () => run(async () => {
  const target = await api('targets/save', {target:JSON.parse($('target-input').value)});
  await refreshTargets(); await loadTarget(target.id); await refresh(); notice(`Target saved as version ${target.version}. Accepted holdings are unchanged.`);
}));
$('target-activate').addEventListener('click', () => run(async () => {
  if (!selectedTarget) throw new Error('Inspect a target first.');
  await api('targets/activate', {target_id:selectedTarget.id,confirm:true}); await loadTarget(selectedTarget.id); await refresh(); notice('Active target changed. Every proposed trade still requires your review and manual execution.');
}));
$('target-archive').addEventListener('click', () => run(async () => {
  if (!selectedTarget) throw new Error('Inspect a target first.');
  await api('targets/archive', {target_id:selectedTarget.id,confirm:true}); await loadTarget(selectedTarget.id); await refresh(); notice('Target archived. Historical versions and plans remain available.');
}));
$('target-diff').addEventListener('click', () => run(async () => {
  if (!selectedTarget) throw new Error('Inspect a target first.');
  const result = await api(`targets/${encodeURIComponent(selectedTarget.id)}/diff?version=${selectedTarget.version}`);
  $('target-drift').replaceChildren(el('h3', 'Target minus accepted holdings'));
  allocationTable($('target-drift'), result.allocations);
  if (result.warnings?.length) $('target-drift').append(el('p',result.warnings.join(' · '),'warnings'));
}));
async function refreshPlans() {
  const result = await api('plans'); const plans = result.plans || [];
  $('plan-list').replaceChildren();
  for (const plan of plans) {
    const row = el('article', undefined, 'saved-row'); const check = el('input'); check.type = 'checkbox'; check.checked = selectedPlanIds.has(plan.id);
    check.setAttribute('aria-label', `Compare ${plan.name}`); check.addEventListener('change', () => check.checked ? selectedPlanIds.add(plan.id) : selectedPlanIds.delete(plan.id));
    const caption = el('div'); caption.append(el('strong', plan.name), el('small', `${plan.created_at} · ${plan.trade_count} proposed trades`));
    row.append(check, caption, statusBadge(plan.status), button('Review plan', () => loadPlan(plan.id))); $('plan-list').append(row);
  }
  if (!plans.length) $('plan-list').append(el('p', 'No plans saved. Generate an alternative from a target above.', 'muted'));
  if (selectedPlan) await loadPlan(selectedPlan);
}
function renderPlan(container, plan) {
  const article = el('article', undefined, 'plan-card'); const header = el('div', undefined, 'section-heading'); header.append(el('h3', plan.name), statusBadge(plan.status)); article.append(header);
  if (plan.status === 'STALE') article.append(el('p', 'Source portfolio changed. Generate a new plan before considering these trades.', 'warnings status-stale'));
  article.append(el('p', 'Every proposed trade requires a human decision and manual execution.', 'muted'));
  article.append(el('p', `Target version ${plan.target?.version || 'Unknown'} · Planning date ${plan.as_of || 'Unknown'} · ${plan.trade_count} proposed trades · Turnover ${money(plan.turnover)}`, 'muted'));
  if (plan.warnings?.length) article.append(el('p', plan.warnings.join(' · '), 'warnings'));
  const tax = plan.tax_analysis || {};
  tableInto(article, ['Realized ST gain/loss','Realized LT gain/loss','Estimated current tax effect'], [[money(tax.short_term_gain_loss),money(tax.long_term_gain_loss),money(tax.estimated_tax_effect)]]);
  article.append(el('h4', 'Proposed manual trades by account'));
  const accountIds = [...new Set((plan.proposed_actions || []).map(action => action.account_id))];
  if (!accountIds.length) article.append(el('p', 'No trades proposed under the known constraints.', 'muted'));
  for (const accountId of accountIds) {
    article.append(el('h4', accountId));
    tableInto(article, ['Action','Security','Quantity','Hypothetical price','Proposed exact lots'], plan.proposed_actions.filter(action => action.account_id === accountId).map(action => [action.type, securityLabel(action.security), action.quantity, money(action.price), action.lot_allocations ? pretty(action.lot_allocations) : 'Not applicable or unresolved; review tax analysis']));
  }
  article.append(el('h4', 'Account cash before and after'));
  tableInto(article, ['Account','Before','After'], Object.keys(plan.cash_before || {}).map(account => [account,money(plan.cash_before[account]),money(plan.cash_after?.[account])]));
  article.append(el('h4', 'Achieved allocation and remaining target drift'));
  allocationTable(article, plan.remaining_target_drift);
  jsonDetails(article, 'Source snapshots, prices and planning assumptions', {source_snapshot_ids:plan.source_snapshot_ids,source_snapshot_dates:plan.source_snapshot_dates,market_data_as_of:plan.market_data_as_of,assumptions:plan.assumptions});
  jsonDetails(article, 'Exposure changes and tax limitations', {exposure:plan.exposure_analysis,tax:plan.tax_analysis});
  const downloads = el('div', undefined, 'actions');
  for (const format of ['markdown','json']) { const link = el('a', `Download ${format} report`, 'file-label'); link.href = `/api/plans/${encodeURIComponent(plan.id)}/report?format=${format}`; link.setAttribute('download',''); downloads.append(link); }
  article.append(downloads); jsonDetails(article, 'Complete saved plan JSON', plan); container.append(article);
}
async function loadPlan(id) {
  const plan = await api(`plans/${encodeURIComponent(id)}`); selectedPlan = id; $('plan-detail').replaceChildren(); renderPlan($('plan-detail'),plan); $('plan-detail').hidden = false;
}
$('plan-form').addEventListener('submit', event => { event.preventDefault(); run(async () => {
  if (!$('plan-target').value) throw new Error('Save and choose a target first.');
  const body = {target_id:$('plan-target').value};
  if ($('plan-date').value) body.as_of = $('plan-date').value;
  if ($('plan-name').value.trim()) body.name = $('plan-name').value.trim();
  if ($('plan-version').value) body.version = parseInt($('plan-version').value,10);
  if ($('plan-prices').value.trim()) body.prices = JSON.parse($('plan-prices').value);
  const trigger = $('plan-generate'); trigger.disabled = true;
  try { const result = await api('plans/generate',body); await refreshPlans(); notice(`Hypothetical plan ${result.plan.name} saved for human review. Choose Review plan to inspect its trades. Accepted holdings are unchanged.`); }
  finally { trigger.disabled = false; }
}); });
$('plan-compare').addEventListener('click', () => run(async () => {
  if (selectedPlanIds.size < 2) throw new Error('Select at least two saved plans.');
  const comparison = await api('plans/compare', {plan_ids:[...selectedPlanIds]}); const container = $('plan-comparison'); container.replaceChildren(el('h3','Alternative comparison'));
  container.append(el('p', `Same source snapshot: ${comparison.same_source_snapshot ? 'Yes' : 'No'} · Same price assumptions: ${comparison.same_price_assumptions ? 'Yes' : 'No'} · Same tax assumptions: ${comparison.same_tax_assumptions ? 'Yes' : 'No'} · Same analysis date: ${comparison.same_analysis_date ? 'Yes' : 'No'}`, 'muted'));
  if (comparison.warnings?.length) container.append(el('p',comparison.warnings.join(' · '),'warnings'));
  tableInto(container, ['Plan','Status','Trades','Turnover','ST gain/loss','LT gain/loss','Estimated tax effect','Maximum drift','Outside tolerance'], comparison.plans.map(plan => [plan.name,plan.status,plan.trade_count,money(plan.turnover),money(plan.tax_summary.short_term_gain_loss),money(plan.tax_summary.long_term_gain_loss),money(plan.tax_summary.estimated_tax_effect),plan.drift_summary.maximum_absolute_weight_drift ?? 'Unknown',plan.drift_summary.positions_outside_tolerance ?? 'Unknown']));
  for (const plan of comparison.plans) {
    const row = el('article', undefined, 'saved-row');
    row.append(el('strong', plan.name), button('Review plan', () => loadPlan(plan.id)));
    if (plan.warnings_preview?.length) row.append(el('p', `${plan.warning_count} warnings: ${plan.warnings_preview.join(' · ')}`, 'warnings'));
    container.append(row);
  }
  container.hidden = false;
}));
async function refreshPrompts() {
  const result = await api('prompts'); const prompts = Array.isArray(result) ? result : result.prompts || [];
  const previous = $('prompt-list').value; $('prompt-list').replaceChildren();
  for (const prompt of prompts) { const option = el('option', `${prompt.title} · ${prompt.source}`); option.value = prompt.id; $('prompt-list').append(option); }
  if (prompts.some(prompt => prompt.id === previous)) $('prompt-list').value = previous;
  if (!promptDirty && $('prompt-list').value) await loadPrompt($('prompt-list').value);
}
async function loadPrompt(id) {
  selectedPrompt = await api(`prompts/${encodeURIComponent(id)}`); promptDirty = false;
  $('prompt-id').value = selectedPrompt.id; $('prompt-content').value = selectedPrompt.content;
  $('prompt-source').textContent = `${selectedPrompt.title} · ${selectedPrompt.source === 'bundled' ? 'Bundled default; saving creates a user override' : 'User prompt'}${selectedPrompt.bundled_available && selectedPrompt.source === 'user' ? ' · bundled default recoverable' : ''}`;
  $('prompt-delete').disabled = selectedPrompt.source !== 'user';
  $('prompt-delete').textContent = selectedPrompt.bundled_available ? 'Delete override · restore default' : 'Delete user prompt';
}
$('prompt-list').addEventListener('change', () => run(() => loadPrompt($('prompt-list').value)));
for (const id of ['prompt-id','prompt-content']) $(id).addEventListener('input', () => {promptDirty = true; $('prompt-delete').disabled = !selectedPrompt || selectedPrompt.id !== $('prompt-id').value || selectedPrompt.source !== 'user';});
$('prompt-new').addEventListener('click', () => {selectedPrompt = null; promptDirty = true; $('prompt-id').value = ''; $('prompt-content').value = '# My review prompt\n\nDescribe the research and financial checks your agent should perform.\n'; $('prompt-source').textContent = 'New user prompt · plain Markdown'; $('prompt-delete').disabled = true; $('prompt-id').focus();});
$('prompt-copy').addEventListener('click', () => run(async () => {
  if (navigator.clipboard?.writeText) {await navigator.clipboard.writeText($('prompt-content').value); notice('Full prompt copied. Paste it into your coding agent.');}
  else {$('prompt-content').focus(); $('prompt-content').select(); notice('Full prompt selected. Use your keyboard copy shortcut, then paste into your coding agent.');}
}));
$('prompt-save').addEventListener('click', () => run(async () => {
  const prompt = await api('prompts/save', {id:$('prompt-id').value,content:$('prompt-content').value}); promptDirty = false;
  await refreshPrompts(); $('prompt-list').value = prompt.id; await loadPrompt(prompt.id); notice('User prompt saved. Bundled defaults remain recoverable.');
}));
$('prompt-delete').addEventListener('click', () => run(async () => {
  if (!selectedPrompt || selectedPrompt.source !== 'user' || selectedPrompt.id !== $('prompt-id').value) throw new Error('Select a saved user prompt before deleting.');
  const result = await api('prompts/delete', {id:selectedPrompt.id}); selectedPrompt = null; promptDirty = false;
  await refreshPrompts(); notice(result.bundled_restored ? 'User override deleted. Bundled default restored.' : 'User prompt deleted.');
}));
function updateNavigation() {
  const active = location.hash || '#overview'; document.querySelectorAll('a.nav').forEach(link => { const selected = link.getAttribute('href') === active; link.classList.toggle('active',selected); if (selected) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
}
window.addEventListener('hashchange',updateNavigation); updateNavigation();
run(refresh);
