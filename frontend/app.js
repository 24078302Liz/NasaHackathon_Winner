'use strict';

const $ = (s, r = document) => r.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const API_BASE = (window.FLAME_API_BASE_URL || document.querySelector('meta[name="flame-api-base"]')?.content || (['localhost','127.0.0.1'].includes(location.hostname) ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '');
const localStudies = INVESTIGATIONS;
let studies = [...localStudies], searchResults = [], selected = [], filter = 'all', query = '', searchMode = 'curated', lastComparison = null;
let saved = new Set(JSON.parse(localStorage.getItem('flame-saved') || '[]'));
const byId = id => studies.find(s => s.id === id) || localStudies.find(s => s.id === id);
const keyFor = id => String(id || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const localFor = id => localStudies.find(s => keyFor(s.id) === keyFor(id) || keyFor(s.name) === keyFor(id) || (keyFor(id)==='saffire' && keyFor(s.name)==='saffirei'));
const readApi = async (path, options) => {
  if (!API_BASE) throw new Error('API 尚未配置');
  const response = await fetch(`${API_BASE}${path}`, {headers:{'Content-Type':'application/json', ...(options?.headers || {})}, ...options});
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch {}
    const detail = payload.detail ?? payload.message ?? payload.error;
    const message = typeof detail === 'string' ? detail : detail?.message || detail?.detail || `HTTP ${response.status}`;
    throw Object.assign(new Error(message), {status:response.status, payload});
  }
  return response.json();
};
function requestErrorMessage(error, action) {
  if (error.status === 502) return `服务暂时不可用（502，${action}工作流失败）：${error.message}`;
  if (error.status === 504) return `服务处理超时（504，${action}工作流超时）：${error.message}`;
  return `${action}失败${error.status ? `（${error.status}）` : ''}：${error.message}`;
}
function toast(message) { const el = $('#toast'); if (el) { el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 3200); } }
function modeLabel() { const pill = $('.demo-pill'); if (pill) pill.innerHTML = `<span></span> ${searchMode === 'api' ? 'Live research API' : 'Curated reference mode'}`; }
function studyFromApi(item) {
  const local = localFor(item.investigation_id) || {};
  const title = item.title || item.investigation_id;
  return {...local, id:item.investigation_id, name:local.name || title, full:local.full || title,
    objective:item.objective || local.objective || 'Objective not yet extracted.',
    description:local.description || item.objective || 'NASA investigation in the connected research corpus.',
    purpose:local.purpose || 'prevention', phase:local.phase || 'solid',
    source:local.source || {id:item.investigation_id,title, publisher:'NASA source record',year:'',doc:'',url:item.source_url || '#',locator:'Investigation record',note:item.objective || '',reviewed:'API record'},
    api:item};
}
function card(s, rank) {
  const result = searchResults.find(r => r.investigation_id === s.id);
  const snippet = result ? `<p class="card-description">${esc(result.relevance_explanation || s.description)}</p>` : `<p class="card-description">${esc(s.description || s.objective)}</p>`;
  const source = s.source || {};
  const checked = selected.includes(s.id);
  return `<article class="investigation-card"><div class="card-visual" style="background:${esc(s.bg || '#eaf0e7')};color:${esc(s.color || '#214e3a')}"><span class="study-logo">${esc((s.name || '?').slice(0,2))}</span><span class="tag">${rank ? `MATCH ${rank}` : esc(s.purpose || 'NASA investigation')}</span></div><div class="card-body"><div class="card-meta"><span class="pill">${esc(s.purpose || 'Research')}</span><span>${esc(source.id || s.id)}</span></div><h2 class="card-title">${esc(s.name || s.id)}</h2><p class="card-subtitle">${esc(s.full || s.title || '')}</p>${snippet}<div class="card-tags"><span>${esc(s.phase || 'NASA')}</span><span>Microgravity research</span></div><div class="card-bottom"><button class="detail-button" data-detail="${esc(s.id)}">Explore investigation →</button><label class="compare-check"><input type="checkbox" data-compare="${esc(s.id)}" ${checked?'checked':''}> Compare</label><button class="save-button ${saved.has(s.id)?'saved':''}" data-save="${esc(s.id)}" aria-label="${saved.has(s.id)?'Unsave':'Save'} ${esc(s.name)}">${saved.has(s.id)?'★':'☆'}</button></div></div></article>`;
}
function visibleStudies() {
  const q = $('#query')?.value.trim().toLowerCase() || '';
  return studies.filter(s => (filter === 'all' || (filter === 'large' ? /large|saffire/i.test(`${s.name} ${s.full}`) : !/large|saffire/i.test(`${s.name} ${s.full}`))) && (!q || `${s.name} ${s.full} ${s.objective} ${s.description}`.toLowerCase().includes(q)));
}
function renderCards(items = visibleStudies()) {
  const cards = $('#cards'); if (!cards) return;
  const studyCount = String(studies.length).padStart(2, '0');
  $('#overviewStudyCount').textContent = studyCount;
  $('#libraryStudyCount').textContent = studyCount;
  $('#navStudyCount').textContent = studies.length;
  cards.innerHTML = items.length ? items.map((s,i) => card(s,i+1)).join('') : '<div class="notice">No matching investigation. Try another question or clear the filters.</div>';
  $('#resultCount').textContent = `${items.length} investigation${items.length===1?'':'s'}`;
}
async function renderDetail(id) {
  let s = byId(id); if (!s) return;
  let record = s.api || null;
  if (API_BASE) {
    try { record = await readApi(`/api/investigations/${encodeURIComponent(id)}`); s = {...s, ...record}; }
    catch (error) { toast(`详情暂时无法读取：${error.message}`); }
  }
  const facts = [['Objective',s.objective],['Research focus',s.api?.research_focus || s.purpose],['Materials',s.materials || s.api?.materials?.join(', ') || 'Not yet extracted'],['Experimental setting',s.setting || 'See linked NASA source'],['Hardware',s.hardware || 'Not yet extracted']];
  const detail = $('#detailContent');
  const docs = record?.documents || [];
  const tests = record?.tests || [];
  const findings = record?.findings || [];
  detail.innerHTML = `<div class="detail-top"><button class="text-button" data-close>Close ×</button><span class="tag">NASA INVESTIGATION</span><h2 id="detailTitle">${esc(s.name || s.id)}</h2><p>${esc(s.full || '')}</p></div><div class="detail-main"><p>${esc(s.description || s.objective || '')}</p><div class="facts">${facts.map(([k,v])=>`<div><small>${esc(k.toUpperCase())}</small>${esc(v || 'Not yet extracted')}</div>`).join('')}</div>${tests.length?`<h3>Experimental conditions</h3><div class="table-wrap"><table><thead><tr><th>Test</th><th>Material</th><th>Geometry</th><th>O₂</th><th>Pressure</th><th>Airflow</th><th>Gravity</th></tr></thead><tbody>${tests.map(t=>`<tr><td>${esc(t.test_id)}</td><td>${esc(t.material)}</td><td>${esc(t.sample_geometry)}</td><td>${esc(t.oxygen_value ?? 'Not yet extracted')} ${esc(t.oxygen_unit||'')}</td><td>${esc(t.pressure_value ?? 'Not yet extracted')} ${esc(t.pressure_unit||'')}</td><td>${esc(t.airflow_value ?? 'Not yet extracted')} ${esc(t.airflow_unit||'')}</td><td>${esc(t.gravity_condition)}</td></tr>`).join('')}</tbody></table></div>`:''}${findings.length?`<h3>Reported findings</h3><ul>${findings.map(f=>`<li>${esc(f.finding_text)} <small>${esc(f.test_id || 'Investigation-level')} · ${esc(f.supporting_evidence_ids?.join(', ') || '')}</small></li>`).join('')}</ul>`:''}${docs.length?`<h3>Source documents</h3><ul>${docs.map(d=>`<li><a href="${esc(d.source_url)}" target="_blank" rel="noopener noreferrer">${esc(d.title)} ↗</a> <small>${esc(d.license_ref||'')}</small></li>`).join('')}</ul>`:''}${s.source?.url && s.source.url !== '#' ? `<a class="source-link" href="${esc(s.source.url)}" target="_blank" rel="noopener noreferrer">Open original NASA source ↗</a>` : ''}</div>`;
  $('#detailDialog').showModal();
}
async function loadLibrary() {
  if (!API_BASE) { modeLabel(); renderCards(); return; }
  try {
    const records = await readApi('/api/investigations');
    if (Array.isArray(records) && records.length) studies = records.map(studyFromApi);
    searchMode = 'api'; modeLabel(); renderCards();
  } catch (error) { searchMode = 'curated'; modeLabel(); renderCards(); toast(`API 暂不可用，显示本地参考资料：${error.message}`); }
}
async function search() {
  query = $('#query').value.trim(); if (!query) { renderCards(); return; }
  if (!API_BASE) { searchMode = 'curated'; const q = query.toLowerCase(); const found = localStudies.filter(s => `${s.name} ${s.full} ${s.terms.join(' ')}`.toLowerCase().includes(q) || q.split(/\W+/).some(t=>t.length>2&&s.terms.some(x=>x.includes(t)))); searchResults=[]; renderCards(found); modeLabel(); toast('Curated keyword match; configure API to enable source-backed AI search.'); return; }
  const button = $('#searchForm button[type="submit"]'); button.disabled = true; button.textContent = 'Searching…';
  try {
    const result = await readApi('/api/search',{method:'POST',body:JSON.stringify({question:query})});
    searchMode='api'; searchResults=result.investigations || [];
    const ranked = searchResults.map(studyFromApi); studies = [...new Map([...studies,...ranked].map(s=>[s.id,s])).values()];
    renderCards(ranked); modeLabel();
    const note = $('#searchNote'); note.hidden=false;
    const passages = result.evidence || [];
    note.innerHTML = `<strong>${esc(result.evidence_status || 'Research response')}</strong><p>${esc(result.answer || 'No answer could be generated from the retrieved evidence.')}</p><small>${(result.citations||[]).map(c=>`[${esc(c.evidence_id)}] ${esc(c.source_url||c.document_id)}`).join(' · ') || 'No citations returned.'}</small>${passages.length?`<div class="api-evidence"><strong>Retrieved evidence (${passages.length})</strong>${passages.map(p=>`<article><small>${esc(p.evidence_id)} · ${esc(p.investigation_id)} · ${esc(p.page ? `page ${p.page}` : p.document_id)}</small><p>${esc(p.text)}</p>${p.source_url?`<a href="${esc(p.source_url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>`:''}</article>`).join('')}</div>`:'<p>No source passages were retrieved for this question.'}`;
  } catch (error) { const note=$('#searchNote'); note.hidden=false; const message=requestErrorMessage(error,'搜索'); note.innerHTML=`<strong>Research request failed</strong><p role="alert">${esc(message)}。你的问题已保留。</p><button type="button" class="secondary" id="retrySearch">Retry</button>`; toast(message); }
  finally { button.disabled=false; button.innerHTML='Search <span>→</span>'; }
}
function updateSelection() {
  $('#navCount').textContent = selected.length;
  const bar=$('#compareBar'); bar.hidden=!selected.length;
  $('#selectionLabel').textContent=`${selected.length} investigation${selected.length===1?'':'s'} selected`;
  $('#openCompare').disabled=selected.length!==2;
}
const COMPARE_FIELDS = [
  'objective','research_focus','materials_or_fuels','sample_geometry','oxygen_concentration',
  'pressure','airflow','gravity_condition','measurements','reported_findings','limitations',
];
const COMPARE_FIELD_LABELS = {
  objective:'Objective', research_focus:'Research focus', materials_or_fuels:'Materials or fuels',
  sample_geometry:'Sample geometry', oxygen_concentration:'Oxygen concentration', pressure:'Pressure',
  airflow:'Airflow', gravity_condition:'Gravity condition', measurements:'Measurements',
  reported_findings:'Reported findings', limitations:'Limitations',
};
const COMPARE_FIELD_ALIASES = {
  objective:['objective'], research_focus:['research_focus','research_area','focus'],
  materials_or_fuels:['materials_or_fuels','materials_fuels','materials_and_fuels','material_fuel','materials','fuels','material','fuel'],
  sample_geometry:['sample_geometry','geometry','sample_size'],
  oxygen_concentration:['oxygen_concentration','oxygen','oxygen_level','oxygen_percentage'],
  pressure:['pressure'], airflow:['airflow','air_flow','flow_rate'],
  gravity_condition:['gravity_condition','gravity','gravity_level'],
  measurements:['measurements','measurement','diagnostics'],
  reported_findings:['reported_findings','findings','reported_finding','results'],
  limitations:['limitations','limitation'],
};
const normalizedDimension = value => String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');
function comparisonValue(raw) {
  const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw.value : raw;
  if (value === null || value === undefined || value === '') return 'Not yet extracted';
  const text = typeof value === 'string' ? value : String(value);
  const unit = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw.unit : null;
  return unit && !text.toLowerCase().includes(String(unit).toLowerCase()) ? `${text} ${unit}` : text;
}
function fieldAvailability(value, provided) {
  if (['reported','not_reported','not_yet_extracted'].includes(provided)) return provided;
  if (/not[ _]reported/i.test(value)) return 'not_reported';
  if (/not[ _](yet[ _])?extracted|not extracted/i.test(value)) return 'not_yet_extracted';
  return 'reported';
}
function normalizeCompareResult(result) {
  const rows = Array.isArray(result?.comparison) ? result.comparison : Array.isArray(result) ? result : [];
  const legacyRows = rows.some(row => row && Object.prototype.hasOwnProperty.call(row,'dimension'));
  const sourceRecords = legacyRows ? [] : rows;
  const requestedIds = selected.slice(0,2);
  const records = requestedIds.map((id,index) => {
    const local = byId(id) || {};
    const sourceRecord = sourceRecords.find(record => record?.investigation_id === id) || sourceRecords[index] || {};
    const fields = COMPARE_FIELDS.map(name => {
      let raw;
      if (legacyRows) {
        const row = rows.find(item => COMPARE_FIELD_ALIASES[name].includes(normalizedDimension(item.dimension)));
        raw = row?.[index === 0 ? 'id_a' : 'id_b'];
      } else {
        const aliases = COMPARE_FIELD_ALIASES[name].map(normalizedDimension);
        raw = sourceRecord.fields?.find(field => aliases.includes(normalizedDimension(field.name)));
      }
      const value = comparisonValue(raw);
      const evidenceIds = raw && typeof raw === 'object' && Array.isArray(raw.evidence_ids) ? raw.evidence_ids : [];
      const availability = fieldAvailability(value, raw?.availability);
      return {name, value, unit:null, availability, evidence_ids:evidenceIds};
    });
    return {
      investigation_id:id,
      title:sourceRecord.title || local.full || local.name || id,
      source_url:sourceRecord.source_url || local.source?.url || '',
      fields,
    };
  });
  return {...(Array.isArray(result) ? {} : result), answer:result?.answer || '',
    evidence_status:result?.evidence_status || 'unknown', comparison:records};
}
function renderCompare() {
  const records=[...studies];
  $('#compareSelectors').innerHTML=[0,1].map(i=>`<label class="select-box">INVESTIGATION ${i+1}<select data-slot="${i}"><option value="">Choose an investigation</option>${records.map(s=>`<option value="${esc(s.id)}" ${selected[i]===s.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label>`).join('');
  $('#comparison').innerHTML='<div class="notice">Select two investigations to compare their available source records.</div>';
  if(selected.length!==2)return;
  $('#comparison').innerHTML='<div class="notice" role="status">Loading source-backed comparison…</div>';
  (async()=>{
    try {
      if(!API_BASE) throw new Error('API not configured');
      const response=await readApi('/api/compare',{method:'POST',body:JSON.stringify({id_a:selected[0],id_b:selected[1]})});
      const result=normalizeCompareResult(response); lastComparison=result; const [a,b]=result.comparison;
      $('#comparison').innerHTML=`<div class="notice"><strong>${esc(result.evidence_status)}</strong><p>${esc(result.answer)}</p></div><div class="table-wrap"><table><thead><tr><th>Research field</th><th>${esc(a.title)}</th><th>${esc(b.title)}</th></tr></thead><tbody>${COMPARE_FIELDS.map((name,i)=>{const fa=a.fields[i],fb=b.fields[i];return `<tr><th>${esc(COMPARE_FIELD_LABELS[name])}</th><td>${esc(fa.value)}<small>${esc(fa.availability)}</small></td><td>${esc(fb.value)}<small>${esc(fb.availability)}</small></td></tr>`;}).join('')}</tbody></table></div>`;
    } catch(error) { const message=requestErrorMessage(error,'对比'); $('#comparison').innerHTML=`<div class="notice" role="alert"><strong>Comparison request failed</strong><p>${esc(message)}。已保留所选调查。</p><button type="button" class="secondary" data-retry-compare>Retry</button></div>`; }
  })();
}
function renderSources() {
  $('#sourceList').innerHTML=studies.map((s,i)=>`<article class="source-card"><span class="source-index">${String(i+1).padStart(2,'0')}</span><div><span class="tag">${esc(s.name || s.id)}</span><h2>${esc(s.source?.title || s.name || s.id)}</h2><small>${esc(s.source?.publisher || 'NASA source record')}</small><p>${esc(s.source?.note || s.objective || '')}</p></div><button class="secondary" data-detail="${esc(s.id)}">Inspect source</button></article>`).join('');
}
function renderSaved() { const items=studies.filter(s=>saved.has(s.id)); $('#savedCards').innerHTML=items.length?items.map(s=>card(s)).join(''):'<div class="notice">No saved investigations yet. Save a card from the library.</div>'; }
function setView() {
  const hash=location.hash.slice(1)||'library'; const view=['library','compare','saved','sources','about'].includes(hash)?hash:'library';
  $$('.view').forEach(el=>el.hidden=el.id!==`view-${view}`); $$('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===view));
  $('#crumb').textContent=({library:'Investigation library',compare:'Compare studies',saved:'Saved investigations',sources:'Source collection',about:'About'})[view];
  if(view==='compare')renderCompare(); if(view==='saved')renderSaved(); if(view==='sources')renderSources();
}
function $$(s,r=document){return [...r.querySelectorAll(s)];}

$('#searchForm').addEventListener('submit',e=>{e.preventDefault();search();});
$('#query').addEventListener('input',()=>{if(!query)renderCards();});
$$('[data-query]').forEach(b=>b.addEventListener('click',()=>{$('#query').value=b.dataset.query;search();}));
$$('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;$$('[data-filter]').forEach(x=>x.classList.toggle('active',x===b));renderCards();}));
$('#clearFilters').addEventListener('click',()=>{filter='all';query='';$('#query').value='';$('#searchNote').hidden=true;$$('[data-filter]').forEach(x=>x.classList.toggle('active',x.dataset.filter==='all'));renderCards();});
$('#explore').addEventListener('click',()=>$('#investigations').scrollIntoView({behavior:'smooth'}));
$('#menu').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
$('#clearSelection').addEventListener('click',()=>{selected=[];updateSelection();renderCards();});
$('#openCompare').addEventListener('click',()=>{location.hash='compare';});
$('#exportCompare').addEventListener('click',()=>{if(!lastComparison?.comparison?.length){toast('Load a comparison before exporting.');return;}const [a,b]=lastComparison.comparison;const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';const fields=[...new Set([...(a.fields||[]).map(f=>f.name),...(b.fields||[]).map(f=>f.name)])];const rows=[['Research field',a.title,b.title],...fields.map(name=>[name,a.fields.find(f=>f.name===name)?.value||'Not yet extracted',b.fields.find(f=>f.name===name)?.value||'Not yet extracted'])];const blob=new Blob([rows.map(r=>r.map(q).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='flame-study-comparison.csv';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);});
document.addEventListener('change',e=>{if(e.target.matches('[data-compare]')){const id=e.target.dataset.compare;if(e.target.checked){if(selected.length===2){e.target.checked=false;toast('Choose up to two investigations.');return;}selected.push(id);}else selected=selected.filter(x=>x!==id);updateSelection();}if(e.target.matches('[data-slot]')){const next=[...selected];next[Number(e.target.dataset.slot)]=e.target.value;selected=[...new Set(next.filter(Boolean))].slice(0,2);updateSelection();renderCompare();}});
document.addEventListener('click',e=>{const detail=e.target.closest('[data-detail]');if(detail)renderDetail(detail.dataset.detail);const close=e.target.closest('[data-close]');if(close)close.closest('dialog').close();const save=e.target.closest('[data-save]');if(save){const id=save.dataset.save;saved.has(id)?saved.delete(id):saved.add(id);localStorage.setItem('flame-saved',JSON.stringify([...saved]));save.textContent=saved.has(id)?'★':'☆';save.classList.toggle('saved',saved.has(id));}});
document.addEventListener('click',e=>{if(e.target.id==='retrySearch')search();if(e.target.matches('[data-retry-compare]'))renderCompare();});
$('#detailDialog').addEventListener('click',e=>{if(e.target===$('#detailDialog'))$('#detailDialog').close();});
window.addEventListener('hashchange',setView);
loadLibrary().then(()=>{renderSources();renderCards();setView();updateSelection();modeLabel();});
