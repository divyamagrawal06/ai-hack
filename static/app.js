/* CareRoute: real local inference via the server, independent immediate client guards. */
"use strict";
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const routeLabel = (route) => ({routine_appointment:"Routine appointment",same_day_human_review:"Same-day human review",emergency_guidance:"Emergency guidance"}[route] || "Assessment pending");
const routeClass = (route) => route === "emergency_guidance" ? "emergency" : route === "same_day_human_review" ? "same-day" : "routine";
const readable = (value) => String(value ?? "Not recorded").replace(/_/g, " ");
const formatTime = (value) => value ? new Date(value).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"}) : "Not recorded";
const state = {fixtures:[], config:null, fixture:null, fixtureDirty:false, loadingFixture:false, clientEvents:[], alertKeys:new Set(), submission:null, submitting:false, generation:0, receipt:null, pollTimer:null, user:null, requests:[], selected:null, reviewDrafts:{}, bookingDrafts:{}, staffPollTimer:null, detailLoad:0, aiStatus:null, aiStatusTimer:null, aiStartedAt:null};
const warningText = {"CHECK-01":"Severe trouble breathing now","CHECK-02":"Severe chest discomfort now","CHECK-03":"Sudden trouble speaking or new one-sided weakness","CHECK-04":"Uncontrolled heavy bleeding now","CHECK-05":"Possible overdose or poisoning now","CHECK-06":"Immediate danger of self-harm"};

// Mirror clinic.policy.PATTERNS and its bounded context filter. This is not a
// universal emergency detector; a negative result never asserts clinical safety.
const warningPatterns = [
  /(?:hard|difficult|trouble|struggling|unable)\s+(?:time\s+)?(?:to\s+)?breath(?:e|ing)/,
  /(?:cannot|can't|can’t)\s+(?:catch\s+my\s+breath|breathe)/,
  /taking\s+a\s+breath\s+is\s+getting\s+harder/,
  /(?:badly\s+wrong|wrong)\s+with\s+my\s+breathing/,
  /(?:severe|crushing|heavy)\s+(?:chest\s+(?:pain|discomfort|pressure)|pressure\s+(?:on|in)\s+my\s+chest)/,
  /(?:bleeding\s+(?:heavily|won't\s+stop|will\s+not\s+stop)|(?:cannot|can't)\s+stop\s+(?:the\s+)?bleeding)/,
  /(?:took|taken|swallowed)\s+(?:far\s+)?too\s+many\s+(?:pills|tablets)/,
  /(?:overdos(?:e|ed|ing)|poisoned)/,
  /(?:sudden(?:ly)?\s+(?:trouble\s+speaking|weakness)|one[- ]sided\s+weakness)/,
  /(?:going\s+to|about\s+to|might)\s+(?:kill|hurt)\s+myself/,
];
function detectLocalWarning(text) {
  if (typeof text !== "string") return "none";
  for (const sentence of text.toLowerCase().replace(/’/g,"'").split(/[.!?\n]+|\bbut\b|\b(?:and\s+)?(?:now|today)\b/)) {
    if (!sentence.trim() || /\b(years? ago|last year|in the past|used to|quoted|quotation|(?:a|my|the) story|character says|example sentence)\b/.test(sentence)) continue;
    for (const pattern of warningPatterns) {
      const match = pattern.exec(sentence);
      if (!match) continue;
      const prefix = sentence.slice(Math.max(0, match.index - 42), match.index).split(/\bbut\b|\band now\b|[,;]/).at(-1);
      if (/\b(?:no|not|never|deny|denies|without|don't|doesn't|isn't|aren't|hasn't)\s+(?:(?:any|having|have|has|had|currently|experiencing|experience|severe|a|very|now)\s+){0,3}$/.test(prefix)) continue;
      return /\b(?:might|may have|maybe|possibly|possible|not sure|cannot tell|can't tell)\b/.test(sentence) ? "current_possible_demo_warning" : "current_explicit_demo_warning";
    }
  }
  return "none";
}
// Exposed only to the local browser test harness, not as a clinical interface.
window.CareRoute = {detectLocalWarning};

function showEmergency(reason, source, detail={}) {
  const firstDisplay = $("immediate-guidance").hidden;
  const key = `${source}:${JSON.stringify(detail)}`;
  if (!state.alertKeys.has(key)) {
    state.alertKeys.add(key);
    state.clientEvents.push({kind:"emergency_guidance_displayed",source,rule:source === "structured" ? "E01" : "E02",timestamp:new Date().toISOString(),detail});
  }
  if ($("immediate-reason").textContent !== reason) $("immediate-reason").textContent = reason;
  $("immediate-guidance").hidden = false;
  if (firstDisplay && !$("view-intake").hidden) $("immediate-guidance").scrollIntoView({block:"start",behavior:"instant"});
}
function checkEmergency() {
  for (const id of Object.keys(warningText)) {
    const answer = document.querySelector(`input[name="${id}"]:checked`)?.value;
    if (answer === "yes" || answer === "unsure") {
      showEmergency(`You selected “${answer === "yes" ? "Yes" : "Unsure"}” for “${warningText[id]}”. Demonstration rule E01 triggered this guidance.`,"structured",{question:id,answer});
      return;
    }
  }
  const signal = detectLocalWarning($("symptom-text").value);
  if (signal !== "none") showEmergency("Your description matched a bounded current-warning check. Demonstration rule E02 triggered this guidance. This is not a diagnosis.","local_text",{signal});
}

async function api(path, options={}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 18000);
  try {
    const response = await fetch(path, {credentials:"same-origin", ...options, signal:controller.signal, headers:{...(options.body ? {"Content-Type":"application/json"} : {}),...options.headers}});
    let data;
    try { data = await response.json(); } catch { throw new Error("The server response could not be confirmed. Please retry safely."); }
    if (!response.ok) {
      const err = new Error(data.error || data.message || `Request failed (${response.status})`);
      err.status = response.status;
      throw err;
    }
    return data;
  } finally { clearTimeout(timer); }
}
function post(path, body, headers={}) { return api(path,{method:"POST",body:JSON.stringify(body),headers}); }
function showView(name) {
  for (const view of document.querySelectorAll(".view")) view.hidden = view.id !== `view-${name}`;
  for (const button of document.querySelectorAll(".nav-button")) {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current");
  }
  if (name === "staff") loadSession();
  window.scrollTo({top:0,behavior:"instant"});
}
for (const button of document.querySelectorAll(".nav-button")) button.addEventListener("click",() => showView(button.dataset.view));

function collectInputs() {
  // Preserve exact saved replay inputs only while the loaded form is unchanged.
  if (state.fixture && !state.fixtureDirty && $("assessment-mode").value === "replay") return structuredClone(state.fixture.inputs);
  const age = $("age").value;
  return {
    symptom_text:$("symptom-text").value,
    preferred_times:$("no-preference").checked ? [] : $("preferred-times").value.split(";").map(x=>x.trim()).filter(Boolean),
    no_time_preference:$("no-preference").checked,
    self_reported_urgency:document.querySelector('input[name="urgency"]:checked')?.value || null,
    age_years:age === "" ? null : Number(age),
    language:$("language").value,
    requester:$("requester").value || null,
    pregnancy_postpartum:$("pregnancy").value === "true" ? true : $("pregnancy").value === "false" ? false : null,
    onset_currentness:$("currentness").value || null,
    onset:$("onset").value,
    emergency_answers:Object.fromEntries(Object.keys(warningText).map(id=>[id,document.querySelector(`input[name="${id}"]:checked`)?.value || "unanswered"])),
  };
}
function updateModeNote() {
  const mode = $("assessment-mode").value;
  const notes = {
    local_ai:["Processed on this computer","AI reads each request and prepares source excerpts for staff review."],
    no_ai:["No AI","Immediate checks can show emergency guidance. Every other request goes to human review because no semantic AI has assessed the description."],
    replay:["Replay — not live AI",state.fixtureDirty ? "This scenario has changed. Reload it for an exact saved replay, or choose structured rules." : "Uses the selected scenario’s authored assessment. It is not a fresh Jev or LLM prediction. Infrastructure failures in the fixture are tested separately, not automatically simulated here."],
    jev_direct:["Live Jev · direct decision","Requests a bounded route or explicit defer. Hard guards and staff review still apply."],
    jev_decomposed:["Live Jev · focused assessments","Requests separate warning, sufficiency, scope and contradiction judgments, then applies policy rules."],
    llm:["Live structured LLM","Requests bounded assessments using the same policy contract. It does not generate medical advice."],
  };
  const [title,body] = notes[mode] || notes.local_ai;
  $("mode-note").innerHTML = `<strong>${escapeHTML(title)}</strong><p>${escapeHTML(body)}</p>`;
}
function setSelect(id, value) {
  const select = $(id);
  const text = value === null || value === undefined ? "" : String(value);
  if (text && !Array.from(select.options).some(o=>o.value === text)) select.add(new Option(readable(text),text));
  select.value = text;
}
function resetRequest(clearFixture=true) {
  state.generation += 1;
  state.submitting = false;
  clearTimeout(state.pollTimer);
  $("intake-form").reset();
  $("intake-form").hidden = false;
  $("new-request").textContent = "Clear form";
  for (const button of document.querySelectorAll("[data-scenario]")) button.classList.remove("selected");
  $("preferred-times").disabled = false;
  $("receipt-panel").hidden = true;
  $("form-error").hidden = true;
  $("immediate-guidance").hidden = true;
  state.clientEvents = [];
  state.alertKeys.clear();
  state.submission = null;
  state.receipt = null;
  state.fixtureDirty = false;
  if (clearFixture) { state.fixture = null; $("fixture-select").value = ""; $("fixture-note").textContent = "44 invented cases to explore."; }
  $("character-count").textContent = "0 / 4,000";
  $("submit-request").disabled = false;
  $("submit-request").textContent = "Review with AI";
  state.aiStartedAt = null;
  updateModeNote();
  updateProgress();
}
function loadFixture() {
  const fixture = state.fixtures.find(c=>c.id === $("fixture-select").value);
  resetRequest(false);
  state.fixture = fixture || null;
  if (!fixture) { $("fixture-note").textContent = "Start a newly invented request."; return; }
  state.loadingFixture = true;
  const inputs = fixture.inputs;
  $("symptom-text").value = inputs.symptom_text || "";
  $("preferred-times").value = (inputs.preferred_times || []).join("; ");
  $("no-preference").checked = inputs.no_time_preference === true;
  $("preferred-times").disabled = $("no-preference").checked;
  $("age").value = inputs.age_years ?? "";
  setSelect("language",inputs.language);
  setSelect("requester",inputs.requester);
  setSelect("currentness",inputs.onset_currentness);
  setSelect("pregnancy", inputs.pregnancy_postpartum === null ? "unknown" : String(inputs.pregnancy_postpartum));
  $("onset").value = inputs.onset || "";
  const urgency = document.querySelector(`input[name="urgency"][value="${inputs.self_reported_urgency}"]`);
  if (urgency) urgency.checked = true;
  for (const [id,answer] of Object.entries(inputs.emergency_answers || {})) {
    const control = document.querySelector(`input[name="${id}"][value="${answer}"]`);
    if (control) control.checked = true;
  }
  $("synthetic-confirm").checked = true;
  $("fixture-note").textContent = `${fixture.id} · ${fixture.title}. Authored synthetic example; not a clinical label.`;
  $("character-count").textContent = `${$("symptom-text").value.length.toLocaleString()} / 4,000`;
  state.loadingFixture = false;
  checkEmergency();
  updateModeNote();
  updateProgress();
}
$("fixture-select").addEventListener("change",loadFixture);
for (const button of document.querySelectorAll("[data-scenario]")) button.addEventListener("click",()=> {
  if (!state.fixtures.length) return;
  $("fixture-select").value = button.dataset.scenario;
  $("assessment-mode").value = "local_ai";
  loadFixture();
  for (const scenario of document.querySelectorAll("[data-scenario]")) scenario.classList.toggle("selected", scenario === button);
  $("symptom-text").focus({preventScroll:true});
});
$("assessment-mode").addEventListener("change",() => { if (!state.submitting && !state.submission?.unknown) state.submission = null; updateModeNote(); });
$("new-request").addEventListener("click",()=> { resetRequest(); $("symptom-text").focus(); });
$("no-preference").addEventListener("change",()=> { $("preferred-times").disabled = $("no-preference").checked; });
$("intake-form").addEventListener("input",(event)=> {
  if (!state.loadingFixture && event.target.id !== "synthetic-confirm") {
    state.fixtureDirty = true;
    // Keep an ambiguous prior submission available for exact retry; edits require
    // an intentional new request instead of accidentally creating a duplicate.
    if (!state.submission?.unknown && !state.submitting) state.submission = null;
  }
  $("character-count").textContent = `${$("symptom-text").value.length.toLocaleString()} / 4,000`;
  checkEmergency();
  updateModeNote();
  updateProgress();
});
$("intake-form").addEventListener("change",checkEmergency);
function formError(message) {
  $("form-error").textContent = message;
  $("form-error").hidden = false;
  $("form-error").focus();
}
$("intake-form").addEventListener("submit",async (event)=> {
  event.preventDefault();
  checkEmergency(); // Always precedes form validation and any network operation.
  $("form-error").hidden = true;
  if (!$("synthetic-confirm").checked) return formError("Confirm that this request uses newly invented information. Do not enter real patient records.");
  const variant = $("assessment-mode").value;
  if (variant === "replay" && (!state.fixture || state.fixtureDirty)) return formError("Replay requires an unchanged synthetic scenario. Reload a scenario or choose structured rules without AI.");
  const age = $("age").value;
  if (age !== "" && (!Number.isInteger(Number(age)) || Number(age) < 0 || Number(age) > 120)) return formError("Use an invented whole-number age between 0 and 120, or leave it blank for human review.");
  const payload = {synthetic:true,inputs:collectInputs(),variant,client_events:structuredClone(state.clientEvents)};
  if (state.fixture && variant === "replay") payload.fixture_id = state.fixture.id;
  if (state.submission?.unknown && JSON.stringify(payload) !== JSON.stringify(state.submission.payload)) return formError("Receipt of your previous attempt is uncertain. Restore the previous inputs and retry, or choose New request intentionally. A new request will not cancel a potentially saved earlier request.");
  if (!state.submission) state.submission = {key:crypto.randomUUID(),payload,unknown:false};
  const submission = state.submission;
  const generation = state.generation;
  state.submitting = true;
  state.aiStartedAt = Date.now();
  const button = $("submit-request");
  button.disabled = true;
  button.textContent = "Sending request…";
  try {
    const result = await post("/api/requests",submission.payload,{"Idempotency-Key":submission.key});
    if (state.generation !== generation) return;
    const request = result.request;
    state.receipt = {id:request.id,token:result.receipt_token || request.receipt_token};
    submission.unknown = false;
    renderReceipt(request);
    $("receipt-panel").focus();
    button.textContent = "Request received";
    pollReceipt();
  } catch(error) {
    if (state.generation !== generation) return;
    const definitelyNotReceived = [400,401,403,413,422].includes(error.status) || /not received|not saved/i.test(error.message);
    submission.unknown = !definitelyNotReceived;
    formError(definitelyNotReceived ? `Your request was not received. ${error.message} No staff were notified. You can retry; emergency guidance remains available.` : `We cannot confirm whether your request was received. ${error.message} Retry with the same information to check safely; do not wait if this may be an emergency.`);
    button.disabled = false;
    button.textContent = "Retry safely →";
  } finally {
    if (state.generation === generation) state.submitting = false;
  }
});
function modeDescription(request) {
  if (request.ai?.status === "partial") return "Partial local AI assessment; warning retained";
  if (request.mode === "replay") return "Replay — authored synthetic assessment, not a live inference";
  if (request.mode === "degraded") return "Degraded — automated assessment unavailable or unusable";
  if (request.mode === "live_model" && request.variant === "local_ai") return `Live local AI — ${request.ai?.model || "Ollama"}`;
  if (request.mode === "live_model") return `Live model — ${readable(request.variant)}`;
  if (request.mode === "no_ai") return "No AI — conservative human review; description not semantically assessed";
  return "Assessment pending — no completed model result";
}
function explanationHTML(decision) {
  if (!decision) return "<p>The assessment is pending. No routine determination has been made.</p>";
  return `<ul>${(decision.explanations || []).map(item=>`<li><strong>${escapeHTML(item.rule)}</strong> · ${escapeHTML(item.text)}</li>`).join("")}</ul>`;
}
function renderReceipt(request) {
  const route = request.route || request.decision?.route;
  const review = request.review_state || request.review_status;
  const booked = request.booking?.state === "booked";
  if (route === "emergency_guidance") showEmergency("The recorded routing decision triggered emergency guidance. Contact local emergency services now; do not wait for staff review.","server_decision",{request_id:request.id,rule:request.decision?.primary_rule || "E02"});
  else if (request.emergency_guidance_ever) showEmergency("Emergency guidance was shown earlier for this request. Its history is preserved; a later staff decision does not retract the immediate guidance already given.","recorded_history",{request_id:request.id});
  const panel = $("receipt-panel");
  panel.hidden = false;
  $("intake-form").hidden = true;
  $("new-request").textContent = "New request";
  panel.innerHTML = `<p class="eyebrow">Saved in the local demonstration</p><h2>${booked ? "Synthetic appointment booked" : "Your request was received"}</h2><p class="receipt-id">Request ${escapeHTML(request.id)}</p><div class="status-grid"><div class="status-item"><small>Request</small><strong>Received</strong></div><div class="status-item"><small>Assessment</small><strong>${escapeHTML(readable(request.assessment_state || request.assessment_status))}</strong></div><div class="status-item"><small>Human review</small><strong>${escapeHTML(readable(review))}</strong></div><div class="status-item"><small>Appointment</small><strong>${booked ? escapeHTML(formatTime(request.booking.slot)) : "Not booked"}</strong></div></div>${aiResultHTML(request)}<div class="suggestion ${routeClass(route)}"><h3>${escapeHTML(routeLabel(route))}</h3>${explanationHTML(request.decision)}</div><p class="small-note"><strong>Information sufficiency:</strong> ${escapeHTML(readable(request.decision?.information_sufficiency || "pending"))}. This is separate from urgency.</p><p class="small-note"><strong>Mode:</strong> ${escapeHTML(modeDescription(request))}</p>${request.coverage?.available === false ? '<div class="message error-message"><strong>Clinic review is unavailable now.</strong> No alternate care contact is configured in this synthetic demo. Do not wait for this form if this may be an emergency.</div>' : '<p class="small-note">Queue coverage is simulated. This demonstration does not provide a real review service.</p>'}<p class="small-note"><strong>No messages were sent.</strong> Notifications are simulated; no clinic or emergency service was contacted.</p><p class="small-note">An administrative suggestion is not a diagnosis or an assurance of safety. ${booked ? "This booking is synthetic only." : "Staff review and a separate booking are still required."}</p><div class="receipt-actions"><button id="review-receipt" type="button" class="button primary">Continue to staff review</button><button id="refresh-receipt" type="button" class="button secondary">Refresh request status</button></div>`;
  $("refresh-receipt").addEventListener("click",pollReceipt);
  $("review-receipt").addEventListener("click",()=>showView("staff"));
}
async function pollReceipt() {
  clearTimeout(state.pollTimer);
  if (!state.receipt) return;
  const receipt = state.receipt;
  const generation = state.generation;
  try {
    const data = await api(`/api/requests/${encodeURIComponent(receipt.id)}?receipt=${encodeURIComponent(receipt.token)}`);
    if (state.generation !== generation || state.receipt !== receipt) return;
    renderReceipt(data.request);
    if (data.request.assessment_state === "pending") state.pollTimer = setTimeout(pollReceipt,700);
  } catch(error) {
    if (state.generation !== generation || state.receipt !== receipt) return;
    const panel = $("receipt-panel");
    const message = document.createElement("p");
    message.className = "error-text";
    message.textContent = `Status refresh failed: ${error.message}. Your earlier receipt remains valid.`;
    panel.append(message);
  }
}

async function loadSession() {
  try { const data = await api("/api/session"); state.user = data.user || null; }
  catch { state.user = null; }
  renderSession();
  if (state.user) loadQueue();
}
function renderSession() {
  $("login-panel").hidden = !!state.user;
  $("staff-workspace").hidden = !state.user;
  $("staff-session").hidden = !state.user;
  if (state.user) $("staff-user").textContent = `${state.user.username} · ${state.user.role}`;
}
$("login-form").addEventListener("submit",async(event)=> {
  event.preventDefault();
  $("login-error").textContent = "";
  try {
    const data = await post("/api/login",{username:$("username").value,password:$("password").value});
    state.user = data.user;
    $("password").value = "";
    renderSession();
    loadQueue();
  } catch(error) { $("login-error").textContent = error.message; }
});
$("logout").addEventListener("click",async()=> {
  try { await post("/api/logout",{}); state.user = null; state.selected = null; renderSession(); }
  catch(error) { staffMessage(error.message,true); }
});
$("refresh-queue").addEventListener("click",loadQueue);
function staffMessage(message,isError=false) {
  const element = $("staff-message");
  element.textContent = message;
  element.hidden = false;
  element.classList.toggle("error-message",isError);
}
async function loadQueue({refreshSelected=true}={}) {
  try {
    const data = await api("/api/queue");
    state.requests = data.requests || [];
    $("queue-count").textContent = `${state.requests.length} synthetic request${state.requests.length === 1 ? "" : "s"} · notifications simulated`;
    const list = $("queue-list");
    list.innerHTML = state.requests.length ? "" : '<div class="form-card empty-state"><h3>No requests yet</h3><p>Submit an invented request from the appointment form to see the staff workflow.</p></div>';
    for (const request of state.requests) {
      const route = request.route || request.decision?.route;
      const card = document.createElement("button");
      card.type = "button";
      card.className = `queue-card${state.selected?.id === request.id ? " active" : ""}`;
      card.dataset.requestId = request.id;
      card.innerHTML = `<div class="queue-card-top"><span class="badge ${routeClass(route)}">${escapeHTML(routeLabel(route))}</span><span class="badge muted">${escapeHTML(readable(request.review_state))}</span></div><h3>Request ${escapeHTML(request.id.slice(0,8))}</h3><p>${escapeHTML((request.inputs?.symptom_text || "No symptom description provided").slice(0,125))}</p><p class="queue-meta">Owner: ${escapeHTML(request.owner || "Unassigned")}<br>${request.overdue ? "Overdue · " : "Review target · "}${escapeHTML(formatTime(request.due_at))}</p>`;
      card.addEventListener("click",()=>loadStaffRequest(request.id));
      list.append(card);
    }
    if (state.selected && refreshSelected) loadStaffRequest(state.selected.id);
  } catch(error) { staffMessage(error.message,true); if (error.status === 401) { state.user=null;renderSession(); } }
}
async function loadStaffRequest(id) {
  const load = ++state.detailLoad;
  clearTimeout(state.staffPollTimer);
  try {
    const data = await api(`/api/requests/${encodeURIComponent(id)}`);
    if (load !== state.detailLoad || !state.user) return;
    state.selected = data.request;
    renderStaffDetail();
    for (const card of document.querySelectorAll(".queue-card")) card.classList.toggle("active",card.dataset.requestId === id);
  } catch(error) { staffMessage(error.message,true); }
}
function renderStaffDetail() {
  const r = state.selected;
  if (!r) return;
  const route = r.route || r.decision?.route;
  const pending = r.assessment_state === "pending";
  const inputs = r.inputs || {};
  const selectedOption = (value) => route === value ? " selected" : "";
  const warnHistory = r.emergency_guidance_ever || (r.client_events || []).length;
  $("staff-detail").innerHTML = `<p class="eyebrow">Request ${escapeHTML(r.id.slice(0,8))} · revision ${escapeHTML(r.input_revision)} · version ${escapeHTML(r.version)}</p><h2>${escapeHTML(routeLabel(route))}</h2><p class="small-note">Received ${escapeHTML(formatTime(r.created_at))} · ${escapeHTML(modeDescription(r))}</p>${warnHistory ? '<div class="message error-message"><strong>Emergency guidance history is preserved.</strong> A later override does not retract advice already shown. Emergency downgrades require a different supervisor’s approval.</div>' : ''}${aiResultHTML(r, true)}<h3>Original description</h3><div class="original-text">${escapeHTML(inputs.symptom_text || "No description provided")}</div><dl class="detail-fields"><div><dt>Self-reported urgency</dt><dd>${escapeHTML(readable(inputs.self_reported_urgency))}</dd></div><div><dt>Information sufficiency</dt><dd>${escapeHTML(readable(r.decision?.information_sufficiency || "pending"))}</dd></div><div><dt>Preferred times</dt><dd>${escapeHTML(inputs.no_time_preference ? "No preference" : (inputs.preferred_times || []).join("; ") || "Not provided")}</dd></div><div><dt>Owner / coverage</dt><dd>${escapeHTML(r.owner || "Unassigned")} · ${r.coverage?.available ? "simulated available" : "unavailable"}</dd></div><div><dt>Review target</dt><dd>${escapeHTML(formatTime(r.due_at))}${r.overdue ? " — overdue" : ""}</dd></div><div><dt>Review / booking</dt><dd>${escapeHTML(readable(r.review_state))} · ${escapeHTML(readable(r.booking?.state))}</dd></div></dl><details><summary>All original structured answers</summary><pre class="json-block">${escapeHTML(JSON.stringify(inputs,null,2))}</pre></details><div class="suggestion ${routeClass(r.decision?.route)}"><h3>Recorded automated / rule suggestion</h3>${explanationHTML(r.decision)}<p class="small-note">Policy ${escapeHTML(r.decision?.policy_version || "pending")} · Actual matches: ${escapeHTML((r.decision?.matched_rules || []).join(", ") || "pending")}</p></div>${r.staff_reviews?.length ? `<details><summary>Human reviews and prior actions (${r.staff_reviews.length})</summary><pre class="json-block">${escapeHTML(JSON.stringify(r.staff_reviews,null,2))}</pre></details>` : ''}<div class="staff-actions"><button id="claim-request" class="button secondary" type="button">Claim request</button><button id="refresh-detail" class="button text-button" type="button">Refresh current version</button></div>${pending ? '<div class="message">Assessment is pending. An authorized human review may take over now; a later model response cannot overwrite it. Emergency guidance does not wait.</div>' : ''}${r.pending_override ? `<div class="message"><strong>Emergency downgrade awaiting a second reviewer.</strong><p>Requested action: ${escapeHTML(routeLabel(r.pending_override.route))}. A different authorized supervisor must approve.</p>${state.user?.role === "supervisor" ? '<button id="approve-override" class="button secondary" type="button">Approve pending override</button>' : ''}</div>` : ''}<form id="review-form" class="detail-section"><h3>Record human review</h3><p>The original suggestion remains in the audit history. A change requires a reason.</p><div class="field-grid"><div><label for="review-route">Administrative action</label><select id="review-route"><option value="routine_appointment"${selectedOption("routine_appointment")}>Routine appointment</option><option value="same_day_human_review"${selectedOption("same_day_human_review")}>Same-day human review</option><option value="emergency_guidance"${selectedOption("emergency_guidance")}>Emergency guidance</option></select></div><div><label for="review-reason">Reason</label><select id="review-reason"><option value="incorrect_input_interpretation">Input interpretation</option><option value="new_information">New information</option><option value="policy_exception">Policy exception</option><option value="coverage_issue">Coverage issue</option><option value="other">Other / confirm suggestion</option></select></div></div><label for="review-comment">Review note</label><textarea id="review-comment" rows="3" maxlength="2000" placeholder="Record the actual reason for your decision." required></textarea><button class="button primary" type="submit">Save review</button></form><form id="booking-form" class="detail-section"><h3>Confirm a synthetic appointment</h3><p>A booking requires completed human review. A suggested route alone does not book a slot.</p><label for="booking-slot">Future appointment time (your displayed timezone)</label><input id="booking-slot" type="datetime-local" required><p class="field-help">Converted to an explicit UTC timestamp for storage. This is a synthetic slot, not a real reservation.</p><button class="button secondary" type="submit" ${r.review_state !== "reviewed" || r.pending_override || r.route === "emergency_guidance" ? "disabled" : ""}>Confirm synthetic booking</button>${r.booking?.state === "booked" ? `<p>Booked: ${escapeHTML(formatTime(r.booking.slot))}</p>` : ''}</form><details id="audit-details" class="detail-section"><summary>Complete immutable audit history</summary><div id="audit-content"><p class="small-note">Open to load the recorded events.</p></div></details>`;
  const draft = state.reviewDrafts[r.id];
  if (draft) {
    $("review-route").value = draft.route;
    $("review-reason").value = draft.reason;
    $("review-comment").value = draft.comment;
  }
  for (const id of ["review-route","review-reason","review-comment"]) $(id).addEventListener("input",()=> {
    state.reviewDrafts[r.id] = {route:$("review-route").value,reason:$("review-reason").value,comment:$("review-comment").value};
  });
  $("claim-request").addEventListener("click",()=>staffAction("claim",{}));
  $("refresh-detail").addEventListener("click",()=>loadStaffRequest(r.id));
  $("review-form").addEventListener("submit",event=> {
    event.preventDefault();
    staffAction("review",{route:$("review-route").value,reason:$("review-reason").value,comment:$("review-comment").value});
  });
  if (state.bookingDrafts[r.id]) $("booking-slot").value = state.bookingDrafts[r.id];
  $("booking-slot").addEventListener("input",()=> { state.bookingDrafts[r.id] = $("booking-slot").value; });
  $("booking-form").addEventListener("submit",event=> {
    event.preventDefault();
    const date = new Date($("booking-slot").value);
    if (!Number.isFinite(date.getTime()) || date <= new Date()) return staffMessage("Choose a valid future synthetic appointment time.",true);
    staffAction("book",{slot:date.toISOString()});
  });
  $("approve-override")?.addEventListener("click",()=>staffAction("approve-override",{}));
  $("audit-details").addEventListener("toggle",()=> { if ($("audit-details").open) loadAudit(r.id); });
  scheduleStaffAssessment();
}
function scheduleStaffAssessment() {
  clearTimeout(state.staffPollTimer);
  if (!state.user || $("view-staff").hidden || state.selected?.assessment_state !== "pending") return;
  const id = state.selected.id;
  state.staffPollTimer = setTimeout(async()=> {
    try {
      const data = await api(`/api/requests/${encodeURIComponent(id)}`);
      if (!state.user || state.selected?.id !== id || $("view-staff").hidden) return;
      if (data.request.version < state.selected.version) return;
      state.selected = data.request;
      if (data.request.assessment_state !== "pending") {
        const focused = document.activeElement;
        const focusId = focused?.id;
        const selection = focused?.tagName === "TEXTAREA" ? [focused.selectionStart,focused.selectionEnd] : null;
        renderStaffDetail();
        if (focusId && $(focusId)) {
          $(focusId).focus({preventScroll:true});
          if (selection) $(focusId).setSelectionRange(...selection);
        }
        loadQueue({refreshSelected:false});
      } else scheduleStaffAssessment();
    } catch {
      // A manual refresh remains available; stop automatic retries on a network error.
    }
  },1000);
}
async function staffAction(action,body) {
  const selected = state.selected;
  if (!selected) return;
  try {
    const data = await post(`/api/requests/${encodeURIComponent(selected.id)}/${action}`,{expected_version:selected.version,...body});
    state.selected = data.request;
    if (action === "review") delete state.reviewDrafts[selected.id];
    if (action === "book") delete state.bookingDrafts[selected.id];
    staffMessage(action === "book" ? "Synthetic appointment booking saved. No external notification was sent." : "Staff action saved with its audit history.");
    renderStaffDetail();
    loadQueue({refreshSelected:false});
  } catch(error) {
    if (error.status === 409) {
      staffMessage(`Your action was not applied. ${error.message} Review the latest state and intentionally resubmit.`,true);
      loadStaffRequest(selected.id);
    } else if (!error.status || error.status >= 500) {
      staffMessage(`We cannot confirm whether your action was saved. ${error.message} Inspect the refreshed record and audit history before retrying. Your review note is preserved.`,true);
      loadStaffRequest(selected.id);
    } else staffMessage(`Your action was not saved: ${error.message}`,true);
  }
}
async function loadAudit(id) {
  try {
    const data = await api(`/api/requests/${encodeURIComponent(id)}/audit`);
    const events = data.events || data.audit || [];
    if (!$("audit-content")) return;
    $("audit-content").innerHTML = `<ol class="audit-list">${events.map(event=>`<li><strong>${escapeHTML(readable(event.event_type || event.kind))}</strong> · ${escapeHTML(event.actor)}<time>${escapeHTML(formatTime(event.timestamp))}</time><pre>${escapeHTML(JSON.stringify(event.payload || event.data || {},null,2))}</pre></li>`).join("")}</ol>`;
  } catch(error) { if ($("audit-content")) $("audit-content").textContent = error.message; }
}

async function initialize() {
  const results = await Promise.allSettled([api("/api/config"),api("/api/fixtures")]);
  if (results[0].status === "fulfilled") {
    state.config = results[0].value;
    for (const item of state.config.variants || []) {
      const option = Array.from($("assessment-mode").options).find(x=>x.value === item.id);
      if (option) { option.disabled = !item.available; option.textContent = item.label + (item.available ? "" : " · unavailable"); }
    }
    for (const item of state.config.emergency_questions || []) if (warningText[item.id]) warningText[item.id] = item.text;
    if (state.config.default_variant && !state.submission) $("assessment-mode").value = state.config.default_variant;
    document.querySelector(".policy-tag strong").textContent = state.config.policy_version || "Policy unavailable";
    document.querySelector("footer>span:last-child").textContent = state.config.policy_version || "Policy unavailable";
  } else {
    document.querySelector(".policy-tag strong").textContent = "Policy unavailable";
    document.querySelector("footer>span:last-child").textContent = "Policy unavailable";
  }
  if (results[1].status === "fulfilled") {
    state.fixtures = results[1].value.cases || results[1].value.fixtures || [];
    for (const fixture of state.fixtures) $("fixture-select").add(new Option(`${fixture.id} · ${fixture.title}`,fixture.id));
  } else $("fixture-note").textContent = "Synthetic scenarios could not be loaded. The emergency notice and immediate checks remain available.";
  updateModeNote();
  refreshAIStatus();
  updateProgress();
}
initialize();
if (window.location.pathname === "/staff") showView("staff");


async function refreshAIStatus() {
  clearTimeout(state.aiStatusTimer);
  const button = $("refresh-ai");
  button.disabled = true;
  try {
    const status = await api("/api/ai/status");
    state.aiStatus = status;
    $("ai-status").textContent = status.available ? "Connected" : status.status === "model_missing" ? "Model needed" : "Offline";
    $("ai-status").className = `model-status ${status.available ? "ready" : "offline"}`;
    $("ai-model").textContent = status.model || "Local language model";
    $("ai-status-message").textContent = status.available ? "Ready for a fresh assessment. No cloud connection needed." : status.message || "Start the local model, then check again. Requests can still go to staff review.";
  } catch {
    $("ai-status").textContent = "Unavailable";
    $("ai-status").className = "model-status offline";
    $("ai-model").textContent = "Local language model";
    $("ai-status-message").textContent = "Cannot reach the AI status service. Check that CareRoute is running, then try again.";
  } finally {
    button.disabled = false;
    state.aiStatusTimer = setTimeout(refreshAIStatus, 15000);
  }
}
$("refresh-ai").addEventListener("click", refreshAIStatus);

function sourceExcerptsHTML(evidence) {
  if (!evidence.length) return "";
  const label = field => field === "onset" ? "When it started" : field === "onset_currentness" ? "Happening now" : !field || field === "symptom_text" ? "Description" : "Request field";
  return `<details class="evidence-details"><summary>Source excerpts (${evidence.length})</summary>${evidence.map(e=>`<blockquote><span class="evidence-source">${escapeHTML(label(e.field))}</span>${escapeHTML(e.quote)}</blockquote>`).join("")}</details>`;
}

function aiResultHTML(request, staff=false) {
  if (request.variant !== "local_ai") return "";
  const ai = request.ai || {};
  const pending = request.assessment_state === "pending" || ai.status === "pending";
  if (pending) {
    const elapsed = state.aiStartedAt ? Math.floor((Date.now() - state.aiStartedAt) / 1000) : 0;
    return `<section class="ai-result pending" aria-label="AI assessment progress"><div class="ai-result-heading"><span class="activity-ring" aria-hidden="true"></span><h3>Local AI is reading the request</h3></div><p>Checking meaning, context and missing details. ${elapsed > 4 ? `${elapsed} seconds elapsed. ` : ""}The first request may take longer while the model loads.</p><div class="processing-steps"><span>Request saved</span><span class="active">AI assessment</span><span>Staff review</span></div><small>Emergency guidance does not wait for the model.</small></section>`;
  }
  if (ai.status === "partial") return `<section class="ai-result partial" role="note"><div class="ai-result-heading"><span aria-hidden="true">!</span><h3>Assessment incomplete</h3></div><p>A possible current warning was identified, but the full assessment could not finish. Follow the emergency guidance shown below; do not wait for staff review.</p><small>The warning is retained. This is not a completed AI assessment.</small></section>`;
  if (ai.status !== "valid") return `<section class="ai-result unavailable"><div class="ai-result-heading"><span aria-hidden="true">!</span><h3>Staff review will take it from here</h3></div><p>${escapeHTML(ai.error || "A valid local AI assessment was not available. Your saved request can still be reviewed by staff.")}</p><small>No AI result has been substituted.</small></section>`;
  const metrics = [ai.model || "Ollama", Number.isFinite(ai.latency_ms) ? `${(ai.latency_ms/1000).toFixed(1)} s` : null, Number.isFinite(ai.completion_tokens) ? `${ai.completion_tokens} output tokens` : null].filter(Boolean);
  const evidence = Array.isArray(ai.evidence) ? ai.evidence : [];
  const fields = request.assessment?.assessment;
  const labels = {warning:"Current warning",intent:"Request intent",information_sufficiency:"Information",contradiction:"Conflicting details",scope:"Demo scope",human_review_indication:"Additional review"};
  const valueLabel = v => v === true ? "Yes" : v === false ? "No" : readable(v);
  return `<section class="ai-result"><div class="ai-result-heading"><span class="ai-icon" aria-hidden="true">✳</span><h3>AI handoff</h3><span class="live-badge">Live inference</span></div><p class="ai-summary">${escapeHTML(ai.summary || "The model assessed the request. Review the original description alongside the routing suggestion.")}</p>${sourceExcerptsHTML(evidence)}${staff && fields ? `<dl class="ai-fields">${Object.entries(labels).map(([key,label])=>`<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(valueLabel(fields[key]))}</dd></div>`).join("")}</dl>` : ""}<div class="ai-metrics">${metrics.map(m=>`<span>${escapeHTML(m)}</span>`).join("")}</div><small>AI-selected excerpts from the request. Staff verify the context.</small></section>`;
}


function updateProgress() {
  const inputs = collectInputs();
  const answered = Object.values(inputs.emergency_answers || {}).filter(x=>["yes","no","unsure"].includes(x)).length;
  const ready = {
    request: !!(inputs.symptom_text?.trim() && inputs.self_reported_urgency && inputs.onset_currentness),
    safety: answered === 6,
    details: inputs.age_years !== null && !!inputs.language && !!inputs.requester && inputs.pregnancy_postpartum !== null && (inputs.no_time_preference || inputs.preferred_times.length > 0),
  };
  let count = Object.values(ready).filter(Boolean).length;
  $("completion-count").textContent = `${count} of 3`;
  $("completion-fill").style.transform = `scaleX(${count/3})`;
  $("progress-request").textContent = ready.request ? "Description added" : "Waiting for details";
  $("progress-safety").textContent = ready.safety ? "All questions answered" : `${6-answered} question${6-answered === 1 ? "" : "s"} to answer`;
  $("progress-details").textContent = ready.details ? "Details added" : "Context and preferences";
  for (const [key,complete] of Object.entries(ready)) document.querySelector(`[data-progress="${key}"]`).classList.toggle("complete",complete);
  $("progress-note").textContent = count === 3 ? "Your details are ready for review. You can still edit any answer." : "Complete what you can. Missing details will be flagged for staff.";
}
for (const link of document.querySelectorAll("[data-progress]")) link.addEventListener("click",event=> {
  if ($("intake-form").hidden) { event.preventDefault(); $("receipt-panel").focus(); }
});


// The same live connection status moves above the form on smaller screens.
const compactConnection = window.matchMedia("(max-width: 1000px)");
function placeConnectionStatus() {
  const panel = document.querySelector(".model-panel");
  if (compactConnection.matches) $("mobile-model-slot").append(panel);
  else document.querySelector(".demo-sidebar").insertBefore(panel,document.querySelector(".next-step-note"));
}
compactConnection.addEventListener("change",placeConnectionStatus);
placeConnectionStatus();
