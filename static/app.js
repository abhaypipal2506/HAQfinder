"use strict";

/* HAQfinder frontend — vanilla JS, no build step.
 * All server-provided text is inserted with textContent / text nodes only.
 */

const API = "/api";

const STATUSES = [
  ["not_started", "Not started"],
  ["in_progress", "In progress"],
  ["submitted", "Submitted"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
];

const $ = (id) => document.getElementById(id);

const alertBox = $("alert");
const findForm = $("find-form");
const situation = $("situation");
const findBtn = $("find-btn");
const voiceBtn = $("voice-btn");
const questionsBox = $("questions-box");
const questionsList = $("questions-list");
const resultsEl = $("results");
const appsTable = $("apps-table");
const appsBody = $("apps-body");
const appsEmpty = $("apps-empty");
const remList = $("reminders-list");
const remEmpty = $("reminders-empty");

let cardSeq = 0;

/* ---------- DOM helpers ---------- */

// el("tag", {attr: value, text: "...", onclick: fn}, child, child, [children])
function el(tag, props, ...children) {
  const node = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = String(v);
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v === true) node.setAttribute(k, "");
      else node.setAttribute(k, String(v));
    }
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false || c === "") continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function showAlert(msg) {
  alertBox.textContent = msg || "";
  alertBox.hidden = !msg;
}

function clearAlert() {
  showAlert("");
}

function humanize(s) {
  const str = String(s || "").replace(/_/g, " ").trim();
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : "";
}

function safeUrl(u) {
  if (typeof u !== "string") return null;
  return /^https?:\/\//i.test(u.trim()) ? u.trim() : null;
}

/* ---------- API ---------- */

function errorMessage(res, data) {
  const d = data && data.detail;
  if (typeof d === "string" && d) return d;
  if (Array.isArray(d) && d.length) {
    return d.map((x) => (x && x.msg) || String(x)).join("; ");
  }
  return `Request failed (${res.status}).`;
}

async function api(path, options = {}) {
  const opts = { ...options, headers: { ...(options.headers || {}) } };
  if (opts.body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  let res;
  try {
    res = await fetch(API + path, opts);
  } catch (e) {
    throw new Error("Network error. Check your connection and try again.");
  }
  if (res.status === 204) return null;
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch (e) { data = null; }
  }
  if (!res.ok) throw new Error(errorMessage(res, data));
  return data;
}

/* ---------- Tabs ---------- */

const tabs = Array.from(document.querySelectorAll('[role="tab"]'));

function activateTab(tab, moveFocus) {
  for (const t of tabs) {
    const selected = t === tab;
    t.setAttribute("aria-selected", String(selected));
    t.tabIndex = selected ? 0 : -1;
    const panel = $(t.getAttribute("aria-controls"));
    if (panel) panel.hidden = !selected;
  }
  if (moveFocus) tab.focus();
  clearAlert();
  if (tab.id === "tab-apps") loadApplications();
  else if (tab.id === "tab-reminders") loadReminders();
}

tabs.forEach((tab, i) => {
  tab.addEventListener("click", () => activateTab(tab, false));
  tab.addEventListener("keydown", (e) => {
    let idx;
    if (e.key === "ArrowRight") idx = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") idx = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") idx = 0;
    else if (e.key === "End") idx = tabs.length - 1;
    else return;
    e.preventDefault();
    activateTab(tabs[idx], true);
  });
});

/* ---------- Find my schemes ---------- */

function collectExtras() {
  const out = {};
  const state = $("f-state").value.trim();
  if (state) out.state = state;
  const age = $("f-age").value;
  if (age !== "") out.age = Number(age);
  const income = $("f-income").value;
  if (income !== "") out.annual_income = Number(income);
  const occ = $("f-occupation").value;
  if (occ !== "any") out.occupation = occ;
  const cat = $("f-category").value;
  if (cat !== "any") out.category = cat;
  const rural = $("f-rural").value;
  if (rural === "yes") out.is_rural = true;
  else if (rural === "no") out.is_rural = false;
  if ($("f-disability").checked) out.has_disability = true;
  const gender = $("f-gender").value;
  if (gender !== "any") out.gender = gender;
  return out;
}

async function resolveSchemes(results) {
  await Promise.all(
    results.map(async (r) => {
      if (r.scheme) return;
      try {
        r.scheme = await api(`/schemes/${encodeURIComponent(r.scheme_id)}`);
      } catch (err) {
        r.scheme = {};
      }
    })
  );
}

function renderQuestions(questions) {
  questionsList.replaceChildren();
  const qs = (questions || []).filter(Boolean);
  questionsBox.hidden = qs.length === 0;
  for (const q of qs) questionsList.append(el("li", {}, q));
}

function statusBadge(status) {
  if (status === "likely_eligible") return el("span", { class: "badge badge-green" }, "Likely eligible");
  if (status === "possibly_eligible") {
    return el("span", { class: "badge badge-amber" }, "Possibly eligible - check missing info");
  }
  return el("span", { class: "badge badge-grey" }, "Not matched");
}

function reasonList(title, items, cls) {
  if (!items || !items.length) return null;
  return el(
    "section",
    { class: "sub" },
    el("h4", {}, title),
    el(
      "ul",
      { class: `reason-list ${cls}` },
      items.map((it) =>
        el(
          "li",
          {},
          el("strong", {}, humanize(it.criterion)),
          it.reason ? `: ${it.reason}` : ""
        )
      )
    )
  );
}

function missingList(items) {
  if (!items || !items.length) return null;
  return el(
    "section",
    { class: "sub" },
    el("h4", {}, "Information that would help"),
    el("ul", { class: "reason-list" }, items.map((m) => el("li", {}, m)))
  );
}

function docsChecklist(docs, uid) {
  if (!docs || !docs.length) return null;
  return el(
    "section",
    { class: "sub" },
    el("h4", {}, "Required documents"),
    el(
      "ul",
      { class: "checklist" },
      docs.map((d, i) => {
        const cid = `${uid}-doc-${i}`;
        return el(
          "li",
          {},
          el("input", { type: "checkbox", id: cid }),
          el("label", { for: cid }, d)
        );
      })
    )
  );
}

function stepsList(steps) {
  if (!steps || !steps.length) return null;
  return el(
    "section",
    { class: "sub" },
    el("h4", {}, "How to apply"),
    el("ol", { class: "steps" }, steps.map((s) => el("li", {}, s)))
  );
}

function buildCard(r) {
  const s = r.scheme || {};
  const uid = `card-${++cardSeq}`;
  const name = s.name || r.scheme_id;

  const liveMsg = el("p", { class: "track-msg", role: "status" });
  const trackBtn = el(
    "button",
    { type: "button", class: "btn btn-primary" },
    "Track this application"
  );
  trackBtn.addEventListener("click", async () => {
    trackBtn.disabled = true;
    liveMsg.textContent = "Saving...";
    try {
      await api("/applications", { method: "POST", body: { scheme_id: r.scheme_id } });
      liveMsg.textContent = `Added "${name}" to My applications.`;
    } catch (err) {
      liveMsg.textContent = err.message;
    } finally {
      trackBtn.disabled = false;
    }
  });

  const links = el("div", { class: "links" });
  const official = safeUrl(s.official_link);
  if (official) {
    links.append(
      el("a", { class: "btn btn-secondary", href: official, target: "_blank", rel: "noopener noreferrer" },
        "Official portal (opens in new tab)")
    );
  }
  const source = safeUrl(s.source_url);
  if (source) {
    links.append(
      el("a", { href: source, target: "_blank", rel: "noopener noreferrer" }, "Source of this information")
    );
  }

  const criteria = [
    reasonList("Criteria you meet", r.matched, "matched"),
    reasonList("Criteria you do not meet", r.failed, "failed"),
  ].filter(Boolean);

  return el(
    "article",
    { class: "card" },
    el("header", { class: "card-head" }, el("h3", {}, name), statusBadge(r.status)),
    s.category ? el("p", { class: "muted" }, "Category: ", el("strong", {}, s.category)) : null,
    s.description ? el("p", {}, s.description) : null,
    criteria.length
      ? el("div", {}, el("h4", { class: "sub" }, "Eligibility criteria"), criteria)
      : null,
    missingList(r.missing_info),
    docsChecklist(s.required_documents, uid),
    stepsList(s.application_steps),
    s.deadline ? el("p", { class: "sub" }, "Deadline: ", el("strong", {}, s.deadline)) : null,
    links,
    el(
      "p",
      { class: "muted sub" },
      "Last verified: ",
      el("strong", {}, s.last_verified || "not recorded")
    ),
    s.verification_note ? el("p", { class: "muted" }, s.verification_note) : null,
    el("div", { class: "track-row" }, trackBtn, liveMsg)
  );
}

function groupSection(title, badgeEl, cards) {
  return el(
    "section",
    { class: "result-group" },
    el("h2", {}, title),
    badgeEl ? el("p", {}, badgeEl) : null,
    el("div", { class: "cards" }, cards)
  );
}

function renderResults(results) {
  resultsEl.replaceChildren();
  if (!results.length) {
    resultsEl.append(el("p", { class: "muted" }, "No schemes were returned. Try adding more detail."));
    return;
  }
  const groups = { likely_eligible: [], possibly_eligible: [], not_matched: [] };
  for (const r of results) {
    (groups[r.status] || groups.not_matched).push(r);
  }

  if (groups.likely_eligible.length) {
    resultsEl.append(
      groupSection("Likely eligible", null, groups.likely_eligible.map(buildCard))
    );
  }
  if (groups.possibly_eligible.length) {
    resultsEl.append(
      groupSection("Possibly eligible", null, groups.possibly_eligible.map(buildCard))
    );
  }
  if (groups.not_matched.length) {
    resultsEl.append(
      el(
        "details",
        { class: "not-matched result-group" },
        el("summary", {}, `Not matched (${groups.not_matched.length})`),
        el("div", { class: "cards" }, groups.not_matched.map(buildCard))
      )
    );
  }
}

async function onFindSubmit(e) {
  e.preventDefault();
  const description = situation.value.trim();
  if (!description) {
    showAlert("Please describe your situation first.");
    situation.focus();
    return;
  }
  const payload = { description, ...collectExtras() };

  findBtn.disabled = true;
  findBtn.setAttribute("aria-busy", "true");
  resultsEl.replaceChildren();
  questionsBox.hidden = true;
  showAlert("Searching schemes... please wait.");
  try {
    const data = await api("/match", { method: "POST", body: payload });
    const results = (data && data.results) || [];
    await resolveSchemes(results);
    renderQuestions(data && data.questions);
    renderResults(results);
    clearAlert();
  } catch (err) {
    showAlert(err.message);
  } finally {
    findBtn.disabled = false;
    findBtn.removeAttribute("aria-busy");
  }
}

findForm.addEventListener("submit", onFindSubmit);

/* Voice input (Web Speech API), hidden when unsupported */
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRec) {
  voiceBtn.hidden = false;
  let recognition = null;
  let listening = false;

  const setListening = (on) => {
    listening = on;
    voiceBtn.textContent = on ? "⏹ Stop listening" : "🎤 Voice input";
    voiceBtn.setAttribute("aria-pressed", String(on));
  };

  voiceBtn.addEventListener("click", () => {
    if (listening && recognition) {
      recognition.stop();
      return;
    }
    try {
      recognition = new SpeechRec();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.onresult = (ev) => {
        const text = Array.from(ev.results)
          .map((r) => (r[0] ? r[0].transcript : ""))
          .join(" ")
          .trim();
        if (!text) return;
        const current = situation.value.trimEnd();
        situation.value = current ? `${current} ${text}` : text;
      };
      recognition.onerror = (ev) => {
        showAlert(`Voice input error: ${ev.error}`);
        setListening(false);
      };
      recognition.onend = () => setListening(false);
      setListening(true);
      recognition.start();
    } catch (err) {
      setListening(false);
      showAlert("Voice input could not start. Please type your situation instead.");
    }
  });
}

/* ---------- My applications ---------- */

async function patchApp(id, body) {
  try {
    const updated = await api(`/applications/${encodeURIComponent(id)}`, { method: "PATCH", body });
    clearAlert();
    return updated;
  } catch (err) {
    showAlert(err.message);
    loadApplications();
    return null;
  }
}

function applicationRow(row) {
  const label = row.scheme_name || row.scheme_id;

  const statusSelect = el(
    "select",
    { "aria-label": `Status for ${label}` },
    STATUSES.map(([value, text]) => el("option", { value, selected: value === row.status }, text))
  );
  statusSelect.addEventListener("change", async () => {
    const updated = await patchApp(row.id, { status: statusSelect.value });
    if (updated) Object.assign(row, updated);
  });

  const notes = el("textarea", { rows: "2", "aria-label": `Notes for ${label}` });
  notes.value = row.notes || "";
  notes.addEventListener("blur", async () => {
    if (notes.value === (row.notes || "")) return;
    const updated = await patchApp(row.id, { notes: notes.value });
    if (updated) Object.assign(row, updated);
  });

  const deadline = el("input", { type: "date", "aria-label": `Deadline for ${label}` });
  deadline.value = row.deadline || "";
  deadline.addEventListener("change", async () => {
    const updated = await patchApp(row.id, { deadline: deadline.value || null });
    if (updated) Object.assign(row, updated);
  });

  const delBtn = el("button", { type: "button", class: "btn btn-danger" }, "Delete");
  delBtn.addEventListener("click", async () => {
    if (!window.confirm(`Delete the tracked application for "${label}"?`)) return;
    try {
      await api(`/applications/${encodeURIComponent(row.id)}`, { method: "DELETE" });
      clearAlert();
      loadApplications();
    } catch (err) {
      showAlert(err.message);
    }
  });

  return el(
    "tr",
    {},
    el("th", { scope: "row" }, label),
    el("td", {}, statusSelect),
    el("td", {}, notes),
    el("td", {}, deadline),
    el("td", {}, row.created_at ? String(row.created_at).slice(0, 10) : ""),
    el("td", {}, delBtn)
  );
}

async function loadApplications() {
  try {
    const rows = (await api("/applications")) || [];
    appsBody.replaceChildren(...rows.map(applicationRow));
    appsEmpty.hidden = rows.length > 0;
    appsTable.hidden = rows.length === 0;
    clearAlert();
  } catch (err) {
    showAlert(err.message);
  }
}

/* ---------- Reminders ---------- */

function daysUntil(isoDate) {
  if (!isoDate) return null;
  const parts = String(isoDate).split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
  const due = new Date(parts[0], parts[1] - 1, parts[2]);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due - today) / 86400000);
}

async function loadReminders() {
  try {
    const rows = (await api("/reminders")) || [];
    remList.replaceChildren();
    for (const row of rows) {
      const days = daysUntil(row.deadline);
      let when;
      let cls = "soon";
      if (days === null) {
        when = "No deadline set";
      } else if (days < 0) {
        when = `Overdue by ${-days} day${-days === 1 ? "" : "s"}`;
        cls = "overdue";
      } else if (days === 0) {
        when = "Due today";
      } else {
        when = `Due in ${days} day${days === 1 ? "" : "s"}`;
      }
      remList.append(
        el(
          "li",
          { class: `reminder ${cls}` },
          el("span", {}, el("strong", {}, row.scheme_name || row.scheme_id)),
          el("span", {}, "Deadline: ", row.deadline || "-"),
          el("span", { class: "when" }, when)
        )
      );
    }
    remEmpty.hidden = rows.length > 0;
    clearAlert();
  } catch (err) {
    showAlert(err.message);
  }
}
