'use strict';

const $ = (s, r = document) => r.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const API_BASE = (window.FLAME_API_BASE_URL || document.querySelector('meta[name="flame-api-base"]')?.content || (['localhost','127.0.0.1'].includes(location.hostname) ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '');
let studies = [], searchResults = [], selected = [], filter = 'all', query = '', lastComparison = null;
let libraryLoading = false, libraryError = null;
let saved;
try { const ids = JSON.parse(localStorage.getItem('flame-saved') || '[]'); saved = new Set(Array.isArray(ids) ? ids : []); } catch { saved = new Set(); }
const byId = id => studies.find(s => s.id === id);
const keyFor = id => String(id || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const readApi = async (path, options) => {
  if (!API_BASE) throw new Error('The API URL is not configured');
  const response = await fetch(`${API_BASE}${path}`, {...options, headers:{'Content-Type':'application/json', ...(options?.headers || {})}, signal:AbortSignal.timeout(190000)});
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
  if (error.status === 502) return `Service unavailable (502, ${action} workflow failed): ${error.message}`;
  if (error.status === 504) return `Request timed out (504, ${action} workflow timed out): ${error.message}`;
  return `${action} failed${error.status ? ` (${error.status})` : ''}: ${error.message}`;
}
function toast(message) { const el = $('#toast'); if (el) { el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 3200); } }
function modeLabel() { const pill = $('.demo-pill'); if (pill) pill.innerHTML = `<span></span> ${libraryLoading ? 'Connecting to research API…' : libraryError ? 'Research API unavailable' : 'Live research API'}`; }
function studyFromApi(item) {
  const title = item.title || item.investigation_id;
  const materials = Array.isArray(item.materials) ? item.materials.join(', ') : item.materials || '';
  return {id:item.investigation_id, name:title, full:title,
    objective:item.objective || 'Objective not yet extracted.', research_focus:item.research_focus || '',
    materials, description:item.objective || item.research_focus || 'NASA investigation in the connected research corpus.',
    purpose:item.research_focus || 'NASA investigation', phase:materials || 'Research record',
    source:{id:item.investigation_id,title, publisher:'NASA Physical Sciences Informatics',year:'',doc:item.doi || '',url:item.source_url || '#',locator:'Investigation record',note:item.research_focus || item.objective || '',reviewed:'API record'},
    api:item};
}
function card(s, rank) {
  const result = searchResults.find(r => r.investigation_id === s.id);
  const snippet = result ? `<p class="card-description">${esc(result.relevance_explanation || s.description)}</p>` : `<p class="card-description">${esc(s.description || s.objective)}</p>`;
  const source = s.source || {};
  const ranking = result ? `<p class="card-description">Rank ${esc(result.rank)} · ${esc(result.hits)} retrieved passages · relevance score ${esc(result.best_score)}. Retrieval relevance is not a safety rating.</p>` : '';
  const checked = selected.includes(s.id);
  return `<article class="investigation-card"><div class="card-visual" style="background:${esc(s.bg || '#eaf0e7')};color:${esc(s.color || '#214e3a')}"><span class="study-logo">${esc((s.name || '?').slice(0,2))}</span><span class="tag">${rank ? `MATCH ${rank}` : esc(s.purpose || 'NASA investigation')}</span></div><div class="card-body"><div class="card-meta"><span class="pill">${esc(s.purpose || 'Research')}</span><span>${esc(source.id || s.id)}</span></div><h2 class="card-title">${esc(s.name || s.id)}</h2><p class="card-subtitle">${esc(s.full || s.title || '')}</p>${snippet}${ranking}<div class="card-tags"><span>${esc(s.phase || 'NASA')}</span><span>Microgravity research</span></div><div class="card-bottom"><button class="detail-button" data-detail="${esc(s.id)}">Explore investigation →</button><label class="compare-check"><input type="checkbox" data-compare="${esc(s.id)}" ${checked?'checked':''}> Compare</label><button class="save-button ${saved.has(s.id)?'saved':''}" data-save="${esc(s.id)}" aria-label="${saved.has(s.id)?'Unsave':'Save'} ${esc(s.name)}">${saved.has(s.id)?'★':'☆'}</button></div></div></article>`;
}
function visibleStudies() {
  const q = $('#query')?.value.trim().toLowerCase() || '';
  return studies.filter(s => (filter === 'all' || (filter === 'large' ? /large|saffire/i.test(`${s.name} ${s.full}`) : !/large|saffire/i.test(`${s.name} ${s.full}`))) && (!q || `${s.name} ${s.full} ${s.objective} ${s.description}`.toLowerCase().includes(q)));
}
function renderCards(items = visibleStudies()) {
  const cards = $('#cards'); if (!cards) return;
  if (libraryLoading) { $('#overviewStudyCount').textContent=$('#libraryStudyCount').textContent=$('#navStudyCount').textContent='…'; $('#resultCount').textContent='Loading…'; cards.innerHTML='<div class="notice" role="status">Loading investigations from the research API…</div>'; return; }
  if (libraryError) { $('#overviewStudyCount').textContent=$('#libraryStudyCount').textContent=$('#navStudyCount').textContent='—'; $('#resultCount').textContent='Unavailable'; cards.innerHTML=`<div class="notice" role="alert"><strong>Could not load investigations</strong><p>${esc(libraryError)}</p><button type="button" class="secondary" id="retryLibrary">Retry</button></div>`; return; }
  const studyCount = String(studies.length).padStart(2, '0');
  $('#overviewStudyCount').textContent = studyCount;
  $('#libraryStudyCount').textContent = studyCount;
  $('#navStudyCount').textContent = studies.length;
  cards.innerHTML = items.length ? items.map((s,i) => card(s,i+1)).join('') : studies.length ? '<div class="notice">No matching investigation. Try another question or clear the filters.</div>' : '<div class="notice" role="status">The API returned no investigations.</div>';
  $('#resultCount').textContent = `${items.length} investigation${items.length===1?'':'s'}`;
}
async function renderDetail(id) {
  let s = byId(id); if (!s) return;
  let record = s.api || null;
  if (API_BASE) {
    try { record = await readApi(`/api/investigations/${encodeURIComponent(id)}`); s = {...s, ...record}; }
    catch (error) { toast(`Unable to load details: ${error.message}`); }
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
  libraryLoading = true; libraryError = null; modeLabel(); renderCards();
  try {
    const records = await readApi('/api/investigations');
    if (!Array.isArray(records)) throw new Error('The investigations API returned an invalid response');
    studies = records.map(studyFromApi);
  } catch (error) { studies=[]; libraryError=requestErrorMessage(error,'Loading investigations'); toast(libraryError); }
  finally { libraryLoading=false; modeLabel(); renderCards(); }
}
async function search() {
  query = $('#query').value.trim(); if (!query) { renderCards(); return; }
  const button = $('#searchForm button[type="submit"]'); button.disabled = true; button.textContent = 'Searching…';
  try {
    const result = await readApi('/api/search',{method:'POST',body:JSON.stringify({question:query})});
    searchResults=result.investigations || [];
    const ranked = searchResults.map(item => byId(item.investigation_id) || studyFromApi(item)); studies = [...new Map([...studies,...ranked].map(s=>[s.id,s])).values()];
    renderCards(ranked); modeLabel();
    const note = $('#searchNote'); note.hidden=false;
    const passages = result.evidence || [];
    note.innerHTML = `<strong>${esc(result.evidence_status || 'Research response')}</strong><div>${markdownAnswer(result.answer || 'No answer could be generated from the retrieved evidence.')}</div><small>${(result.citations||[]).map(c=>`[${esc(c.evidence_id)}] ${esc(c.source_url||c.document_id)}`).join(' · ') || 'No citations returned.'}</small>${passages.length?`<div class="api-evidence"><strong>Retrieved evidence (${passages.length})</strong>${passages.map(p=>`<article><small>${esc(p.evidence_id)} · ${esc(p.investigation_id)} · ${esc(p.page ? `page ${p.page}` : p.document_id)}</small><p>${esc(p.text)}</p>${p.source_url?`<a href="${esc(p.source_url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>`:''}</article>`).join('')}</div>`:'<p>No source passages were retrieved for this question.'}`;
  } catch (error) { const note=$('#searchNote'); note.hidden=false; const message=requestErrorMessage(error,'Search'); note.innerHTML=`<strong>Research request failed</strong><p role="alert">${esc(message)}. Your question has been preserved.</p><button type="button" class="secondary" id="retrySearch">Retry</button>`; toast(message); }
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
  objective:['objective','objectives'], research_focus:['research_focus','research_area','focus'],
  materials_or_fuels:['materials_or_fuels','materials_fuels','materials_and_fuels','material_fuel','fuels_materials','materials','fuels','material','fuel'],
  sample_geometry:['sample_geometry','geometry','sample_size'],
  oxygen_concentration:['oxygen_concentration','oxygen','oxygen_level','oxygen_percentage'],
  pressure:['pressure'], airflow:['airflow','air_flow','flow_rate','gas_flow','flow'],
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
function legacyComparisonValue(row, id, index, local) {
  const directKey = index === 0 ? 'id_a' : 'id_b';
  if (Object.prototype.hasOwnProperty.call(row,directKey)) return row[directKey];
  const acceptedKeys = new Set([id,local.id,local.name,local.full].filter(Boolean).map(keyFor));
  const match = Object.keys(row).find(key => key !== 'dimension' && acceptedKeys.has(keyFor(key)));
  return match ? row[match] : undefined;
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
        const aliases = COMPARE_FIELD_ALIASES[name].map(normalizedDimension);
        const row = rows.find(item => aliases.includes(normalizedDimension(item.dimension)));
        raw = row ? legacyComparisonValue(row,id,index,local) : undefined;
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
function markdownInline(value) {
  return esc(value).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
}
function markdownAnswer(markdown) {
  const lines=String(markdown || '').split(/\r?\n/), output=[];
  let paragraph=[], list=[], index=0;
  const flushParagraph=()=>{if(paragraph.length){output.push(`<p>${markdownInline(paragraph.join(' '))}</p>`);paragraph=[];}};
  const flushList=()=>{if(list.length){output.push(`<ul>${list.map(item=>`<li>${markdownInline(item)}</li>`).join('')}</ul>`);list=[];}};
  const cells=line=>line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(cell=>cell.trim());
  while(index<lines.length){
    const line=lines[index].trim();
    if(!line){flushParagraph();flushList();index++;continue;}
    if(line.includes('|') && index+1<lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index+1])){
      flushParagraph();flushList();const headers=cells(line);index+=2;const rows=[];
      while(index<lines.length && lines[index].includes('|')){rows.push(cells(lines[index]));index++;}
      output.push(`<div class="table-wrap"><table><thead><tr>${headers.map(cell=>`<th>${markdownInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${headers.map((_,cellIndex)=>`<td>${markdownInline(row[cellIndex] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    const heading=line.match(/^(#{1,3})\s+(.+)$/);
    if(heading){flushParagraph();flushList();const level=Math.min(heading[1].length+2,5);output.push(`<h${level}>${markdownInline(heading[2])}</h${level}>`);index++;continue;}
    const bullet=line.match(/^[-*]\s+(.+)$/);
    if(bullet){flushParagraph();list.push(bullet[1]);index++;continue;}
    flushList();paragraph.push(line);index++;
  }
  flushParagraph();flushList();return output.join('');
}
function renderCompare() {
  const records=[...studies];
  $('#compareSelectors').innerHTML=[0,1].map(i=>`<label class="select-box">INVESTIGATION ${i+1}<select data-slot="${i}"><option value="">Choose an investigation</option>${records.map(s=>`<option value="${esc(s.id)}" ${selected[i]===s.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label>`).join('');
  $('#comparison').innerHTML='<div class="notice">Select two investigations to compare their available source records.</div>';
  lastComparison = null;
  if(selected.length!==2)return;
  $('#comparison').innerHTML='<div class="notice" role="status">Loading source-backed comparison…</div>';
  (async()=>{
    try {
      if(!API_BASE) throw new Error('API not configured');
      const requested = selected.join('|');
      const response=await readApi('/api/compare',{method:'POST',body:JSON.stringify({id_a:selected[0],id_b:selected[1]})});
      if (requested !== selected.join('|')) return;
      const result=normalizeCompareResult(response); lastComparison=result; const [a,b]=result.comparison;
      $('#comparison').innerHTML=`<section class="notice"><strong>Evidence status: ${esc(result.evidence_status)}</strong><div class="compare-answer">${markdownAnswer(result.answer)}</div></section><div class="table-wrap"><table><thead><tr><th>Research field</th><th>${esc(a.title)}</th><th>${esc(b.title)}</th></tr></thead><tbody>${COMPARE_FIELDS.map((name,i)=>{const fa=a.fields[i],fb=b.fields[i];return `<tr><th>${esc(COMPARE_FIELD_LABELS[name])}</th><td>${esc(fa.value)}<small>${esc(fa.availability)}</small></td><td>${esc(fb.value)}<small>${esc(fb.availability)}</small></td></tr>`;}).join('')}</tbody></table></div>`;
    } catch(error) { const message=requestErrorMessage(error,'Comparison'); $('#comparison').innerHTML=`<div class="notice" role="alert"><strong>Comparison request failed</strong><p>${esc(message)}. Your selected investigations have been preserved.</p><button type="button" class="secondary" data-retry-compare>Retry</button></div>`; }
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
document.addEventListener('click',e=>{const detail=e.target.closest('[data-detail]');if(detail)renderDetail(detail.dataset.detail);const close=e.target.closest('[data-close]');if(close)close.closest('dialog').close();const save=e.target.closest('[data-save]');if(save){const id=save.dataset.save;saved.has(id)?saved.delete(id):saved.add(id);try { localStorage.setItem('flame-saved',JSON.stringify([...saved])); } catch { toast('Browser storage is unavailable; saved items will last for this session.'); }save.textContent=saved.has(id)?'★':'☆';save.classList.toggle('saved',saved.has(id));}});
document.addEventListener('click',e=>{if(e.target.id==='retrySearch')search();if(e.target.id==='retryLibrary')loadLibrary();if(e.target.matches('[data-retry-compare]'))renderCompare();});
$('#detailDialog').addEventListener('click',e=>{if(e.target===$('#detailDialog'))$('#detailDialog').close();});
window.addEventListener('hashchange',setView);
loadLibrary().then(()=>{renderSources();renderCards();setView();updateSelection();modeLabel();});
