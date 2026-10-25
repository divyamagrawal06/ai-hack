"use strict";
const reportImport = {file:null, result:null, objectURL:null, generation:0, busy:false};
const reportLabels = {age_at_report:"Age at report",report_date:"Report date",symptoms:"Reported symptoms",onset:"Reported onset",medical_history:"Reported history",medications:"Recorded medications",allergies:"Recorded allergies",test_results:"Reported test results",follow_up:"Documented follow-up"};
const reportIssueLabels = {missing_date:"Report date missing: currentness cannot be established.",illegible_content:"Some content is illegible; verify the original.",conflicting_details:"Conflicting details need human review.",no_clinical_content:"No usable clinical content was identified."};
const reportMimes = {pdf:"application/pdf",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg",txt:"text/plain"};
function reportMessage(text, error=false) {
  $("report-message").textContent = text;
  $("report-message").className = error ? "error-text" : "field-help";
}
async function reportStatus() {
  try {
    const data = await api('/api/reports/status');
    $("report-status").textContent = data.configured ? `OpenAI configured · ${data.model} · cloud extraction` : 'Add your server key in var/openai-api-key.txt or OPENAI_API_KEY. No key goes in the browser.';
  } catch (error) { $("report-status").textContent = error.message; }
}
function selectReport(file) {
  reportImport.generation++;
  reportImport.file = file;
  reportImport.result = null;
  $("report-preview").hidden = true;
  $("report-reviewed").checked = false;
  $("report-consent").checked = false;
  if (reportImport.objectURL) URL.revokeObjectURL(reportImport.objectURL);
  $("report-original").hidden = !file;
  if (file) {
    const type = reportMimes[file.name.split('.').at(-1).toLowerCase()] || 'application/octet-stream';
    reportImport.objectURL = URL.createObjectURL(new Blob([file], {type}));
    $("report-original").href = reportImport.objectURL;
  }
  $("report-file-note").textContent = file ? `${file.name} · ${(file.size/1024).toFixed(1)} KiB` : 'No report selected.';
  reportMessage('');
}
$("report-file").addEventListener('change', () => { $("report-sample").value = ''; selectReport($("report-file").files[0] || null); });
$("report-sample").addEventListener('change', async () => {
  const name = $("report-sample").value;
  const generation = ++reportImport.generation;
  if (!name) return selectReport(null);
  try {
    const response = await fetch('/samples/' + encodeURIComponent(name));
    if (!response.ok) throw new Error('The sample could not be loaded.');
    const blob = await response.blob();
    if (generation !== reportImport.generation) return;
    $("report-file").value = '';
    selectReport(new File([blob], name, {type:blob.type}));
  } catch (error) { if (generation === reportImport.generation) reportMessage(error.message, true); }
});
function asBase64(file) {
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('The file could not be read.'));
    reader.readAsDataURL(file);
  });
}
$("report-extract").addEventListener('click', async () => {
  const file = reportImport.file;
  if (!file) return reportMessage('Choose a report or sample first.', true);
  if (file.size > 4*1024*1024 || file.size === 0) return reportMessage('Use a nonempty report up to 4 MiB.', true);
  if (!$("report-consent").checked) return reportMessage('Confirm invented content and consent to sending it to OpenAI.', true);
  if (reportImport.busy) return;
  const generation = reportImport.generation;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  reportImport.busy = true;
  $("report-extract").disabled = true;
  $("report-file").disabled = true;
  $("report-sample").disabled = true;
  $("report-preview").hidden = true;
  reportImport.result = null;
  reportMessage('Extracting with OpenAI. This can take up to a minute; nothing has been added to intake.');
  try {
    const encoded = await asBase64(file);
    const response = await fetch('/api/reports/extract', {method:'POST', credentials:'same-origin', signal:controller.signal,
      headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name,data_base64:encoded,synthetic:true,send_to_openai:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Extraction failed.');
    if (generation !== reportImport.generation) return;
    reportImport.result = data;
    const report = data.report;
    $("report-provenance").textContent = `${report.filename} · OpenAI ${report.model} · ${(report.latency_ms/1000).toFixed(1)} s · ${report.usage.output_tokens ?? 'unknown'} output tokens`;
    $("report-facts").innerHTML = report.extraction.facts.map(fact => `<article class="report-fact"><strong>${escapeHTML(reportLabels[fact.field])}</strong><p>${escapeHTML(fact.value)}</p><blockquote>${escapeHTML(fact.quote)}</blockquote><small>${escapeHTML(readable(fact.time_context))}${fact.page ? ` · page ${fact.page}` : ''} · ${fact.quote_verification === 'normalized_text_match' ? 'Matched source text (whitespace normalized)' : 'Model transcription — visually verify'}</small></article>`).join('');
    $("report-issues").textContent = report.extraction.issues.map(issue=>issue === 'missing_date' && report.extraction.facts.some(f=>f.field === 'report_date') ? 'The AI flagged a missing date despite extracting one. Verify the date against the original.' : reportIssueLabels[issue]).join(' ');
    $("report-draft").value = 'Quoted report context only; current symptoms and request intent must be confirmed separately.\n' + report.extraction.facts.map(fact=>`Quoted report / ${readable(fact.time_context)} / ${reportLabels[fact.field]}: ${fact.quote}`).join('\n');
    $("report-reviewed").checked = false;
    $("report-apply").disabled = report.extraction.facts.length === 0;
    $("report-preview").hidden = false;
    reportMessage(report.extraction.facts.length ? 'Extraction ready for your review. No intake fields have changed.' : 'No usable facts were extracted. Nothing can be imported.', !report.extraction.facts.length);
  } catch (error) {
    reportMessage(error.name === 'AbortError' ? 'Extraction timed out. Nothing was imported. Check the server before retrying.' : error.message, true);
  } finally {
    clearTimeout(timer);
    reportImport.busy = false;
    $("report-extract").disabled = false;
    $("report-file").disabled = false;
    $("report-sample").disabled = false;
  }
});
$("report-reviewed").addEventListener('change', () => {
  if ($("report-reviewed").checked) reportMessage('Review confirmed. Use the notes in a new request when ready.');
});
$("report-apply").addEventListener('click', () => {
  if (!reportImport.result || !$("report-reviewed").checked) return reportMessage('Compare the extracted notes with the original and confirm your review first.', true);
  const draft = $("report-draft").value.trim();
  if (!draft || draft.length > 4000) return reportMessage('Reviewed notes must contain 1–4,000 characters.', true);
  const previousEvents = structuredClone(state.clientEvents);
  resetRequest();
  state.clientEvents = previousEvents;
  $("symptom-text").value = draft;
  state.reportId = reportImport.result.report_id;
  $("assessment-mode").value = 'local_ai';
  $("synthetic-confirm").checked = true;
  $("report-attached").textContent = `Reviewed report attached: ${reportImport.result.report.filename}. Add what you need today and answer all current-status questions below.`;
  $("report-attached").hidden = false;
  $("symptom-text").dispatchEvent(new Event('input', {bubbles:true}));
  if (previousEvents.length) showEmergency('Emergency guidance was already shown before this report import. It remains flagged for staff review.', 'local_text', {signal:'current_possible_demo_warning'});
  $("report-import").open = false;
  $("symptom-text").focus();
});
reportStatus();
