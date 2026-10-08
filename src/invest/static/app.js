'use strict';
const $ = id => document.getElementById(id);
let snapshot = null;
let activityPreview = null;
const pretty = value => JSON.stringify(value, null, 2);
let displayCurrency = 'USD';
const money = value => new Intl.NumberFormat('en-US', {style:'currency', currency:displayCurrency}).format(Number(value || 0));
function notice(message, error=false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = false; }
async function api(path, body) {
  const response = await fetch('/api/' + path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed');
  return value;
}
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
async function refresh() {
  const [summary, state] = await Promise.all([api('summary'), api('state')]);
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
}
function clearPreview() { snapshot = null; $('preview-area').hidden = true; $('reconcile-area').hidden = true; $('accept-confirm').checked = false; $('apply').disabled = true; }
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
  snapshot = await api('import',body); $('preview-json').textContent = pretty(snapshot); $('preview-area').hidden=false;
  $('html-input').value=''; $('html-file').value=''; notice('Preview ready. The ledger has not changed. Review the values, then compare with your ledger.');
}); });
$('reconcile').addEventListener('click',()=>run(async()=>{
  if (!snapshot) throw new Error('Preview an account page first.');
  const result = await api('reconcile',{snapshot}); $('reconcile-json').textContent=pretty(result); $('reconcile-area').hidden=false;
}));
$('accept-confirm').addEventListener('change',()=>{$('apply').disabled=!$('accept-confirm').checked;});
$('apply').addEventListener('click',()=>run(async()=>{
  if (!$('accept-confirm').checked || !snapshot) throw new Error('Review and confirm the snapshot first.');
  await api('apply',{snapshot,confirm:true}); clearPreview(); await refresh(); notice('Snapshot accepted. Your local ledger has been updated.');
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
run(refresh);
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
