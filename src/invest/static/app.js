'use strict';
const $ = id => document.getElementById(id);
let snapshot = null;
let activityPreview = null;
const pretty = value => JSON.stringify(value, null, 2);
const money = value => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'}).format(Number(value || 0));
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
