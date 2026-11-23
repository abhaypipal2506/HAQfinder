"use strict";

const API = "/api";
const PAGE_SIZE = 9;
const $ = (id) => document.getElementById(id);
const state = {
  user: null,
  profile: {},
  bookmarks: new Set(),
  category: "",
  search: "",
  governmentState: "",
  page: 1,
  totalPages: 1,
  specialAnswers: {},
  lastMatch: null,
  toastTimer: null,
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function button(text, className, action, label) {
  const element = node("button", className, text);
  element.type = "button";
  if (label) element.setAttribute("aria-label", label);
  element.addEventListener("click", action);
  return element;
}

function safeUrl(value) {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function humanize(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const request = { ...options, headers, credentials: "same-origin" };
  if (request.body !== undefined) {
    headers["Content-Type"] = "application/json";
    request.body = JSON.stringify(request.body);
  }
  let response;
  try {
    response = await fetch(API + path, request);
  } catch {
    throw new Error("Could not reach HAQfinder. Check your connection and try again.");
  }
  if (response.status === 204) return null;
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error("The server returned an unexpected response.");
    }
  }
  if (!response.ok) {
    const detail = data && data.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || "Invalid input").join("; ")
      : detail;
    throw new Error(message || `Request failed (${response.status}).`);
  }
  return data;
}

function toast(message, error = false) {
  const element = $("toast");
  element.textContent = message;
  element.classList.toggle("toast-error", error);
  element.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    element.hidden = true;
  }, 4200);
}

function dialog(id) {
  return $(id);
}

function openAuth(mode = "login") {
  switchAuthMode(mode);
  dialog("auth-dialog").showModal();
  $("auth-message").textContent = "";
}

function switchAuthMode(mode) {
  const isRegister = mode === "register";
  $("auth-title").textContent = isRegister ? "Make space for your next step." : "Welcome back.";
  $("login-form").hidden = isRegister;
  $("register-form").hidden = !isRegister;
  document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
    const selected = tab.dataset.authMode === mode;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
}

function renderAccount() {
  $("account-name").hidden = !state.user;
  $("account-name").textContent = state.user ? `Hello, ${state.user.full_name.split(/\s+/)[0]}` : "";
  $("login-open").hidden = Boolean(state.user);
  $("logout-button").hidden = !state.user;
  $("profile-save-hint").textContent = state.user
    ? "Your profile is saved to your account."
    : "Sign in to save your profile.";
  for (const [field, id] of Object.entries({
    age: "profile-age",
    state: "profile-state",
    district: "profile-district",
    occupation: "profile-occupation",
    annual_income: "profile-income",
    category: "profile-category",
    education: "profile-education",
    gender: "profile-gender",
    family_situation: "profile-family",
  })) {
    if (state.profile[field] !== undefined && state.profile[field] !== null) {
      $(id).value = String(state.profile[field]);
    }
  }
  $("profile-rural").value = typeof state.profile.is_rural === "boolean"
    ? String(state.profile.is_rural)
    : "";
  $("profile-disability").value = typeof state.profile.has_disability === "boolean"
    ? String(state.profile.has_disability)
    : "";
}

async function loadAccount() {
  try {
    const data = await api("/auth/me");
    state.user = data.user;
    state.profile = data.profile || {};
  } catch (error) {
    state.user = null;
    state.profile = {};
    toast(error.message, true);
  }
  renderAccount();
  await loadWorkspace();
}

function getProfileFields() {
  const fields = {};
  const textFields = {
    state: "profile-state",
    district: "profile-district",
    occupation: "profile-occupation",
    category: "profile-category",
    education: "profile-education",
    gender: "profile-gender",
    family_situation: "profile-family",
  };
  for (const [key, id] of Object.entries(textFields)) {
    const value = $(id).value.trim();
    if (value) fields[key] = value;
  }
  for (const [key, id] of [["age", "profile-age"], ["annual_income", "profile-income"]]) {
    if ($(id).value !== "") fields[key] = Number($(id).value);
  }
  for (const [key, id] of [["is_rural", "profile-rural"], ["has_disability", "profile-disability"]]) {
    if ($(id).value !== "") fields[key] = $(id).value === "true";
  }
  return fields;
}

function addSourceLink(container, label, value) {
  const url = safeUrl(value);
  if (!url) return;
  const link = node("a", "source-link", `${label} ↗`);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  container.append(link);
}

function showSchemeDetails(scheme) {
  const detail = $("scheme-detail");
  detail.replaceChildren();
  detail.append(node("p", "eyebrow eyebrow-dark", `${humanize(scheme.category)} · ${scheme.state || "Central"}`));
  const title = node("h2", "detail-title", scheme.name || scheme.id);
  title.id = "detail-title";
  detail.append(title);
  detail.append(node("p", "detail-description", scheme.description || "No summary is recorded in the catalogue."));

  const metadata = node("div", "detail-meta");
  const level = scheme.government_level || (scheme.state ? "State" : "Central");
  const verification = scheme.verification_status || "MANUAL REVIEW REQUIRED";
  metadata.append(
    node("span", "detail-chip", `${humanize(level)} scheme`),
    node("span", "detail-chip verification-chip", `Source: ${humanize(verification)}`),
    node("span", "detail-chip", scheme.last_verified
      ? `Last recorded review: ${scheme.last_verified}`
      : "Last review date not recorded")
  );
  detail.append(metadata);

  const facts = node("div", "detail-facts");
  const addFact = (titleText, content) => {
    const section = node("section", "detail-fact");
    section.append(node("h3", "", titleText));
    if (Array.isArray(content)) {
      if (content.length) {
        const list = node("ul", "");
        content.forEach((value) => list.append(node("li", "", value)));
        section.append(list);
      } else {
        section.append(node("p", "muted-copy", "Not listed in the current record."));
      }
    } else {
      section.append(node("p", "", content || "Not listed in the current record."));
    }
    facts.append(section);
  };

  addFact("Department", scheme.department || "Not listed in the current record.");
  addFact("State applicability", scheme.state || "Central scheme; state-specific availability should be confirmed.");
  addFact("Benefits", scheme.benefits || scheme.benefit || []);
  const criteria = scheme.eligibility_criteria;
  addFact("Eligibility", Array.isArray(criteria) && criteria.length
    ? criteria
    : Object.entries(scheme.eligibility || {}).map(([key, value]) => `${humanize(key)}: ${Array.isArray(value) ? value.join(", ") : value}`));
  addFact("Documents usually requested", scheme.required_documents || []);
  addFact("Application steps", scheme.application_steps || []);
  if (scheme.deadline) addFact("Deadline", scheme.deadline);
  detail.append(facts);

  const links = node("div", "detail-links");
  addSourceLink(links, "Official scheme information", scheme.official_information_url || scheme.official_link);
  addSourceLink(links, "Apply on the official portal", scheme.application_url || scheme.official_link);
  addSourceLink(links, "Source record", scheme.source_url);
  detail.append(links);

  if (scheme.verification_note || scheme.notes) {
    detail.append(node("p", "verification-note", scheme.verification_note || scheme.notes));
  }
  dialog("scheme-dialog").showModal();
}

function eligibilityBadge(status) {
  const label = {
    likely_eligible: "Possible fit",
    possibly_eligible: "More information needed",
    not_matched: "Not matched",
  }[status] || humanize(status);
  const badge = node("span", `eligibility-badge eligibility-${status || "unknown"}`, label);
  return badge;
}

async function toggleBookmark(scheme) {
  if (!state.user) {
    openAuth("login");
    toast("Log in to save schemes to your personal list.");
    return;
  }
  const saved = state.bookmarks.has(scheme.id);
  try {
    if (saved) {
      await api(`/bookmarks/${encodeURIComponent(scheme.id)}`, { method: "DELETE" });
      state.bookmarks.delete(scheme.id);
      toast("Scheme removed from your saved list.");
    } else {
      await api(`/bookmarks/${encodeURIComponent(scheme.id)}`, { method: "PUT" });
      state.bookmarks.add(scheme.id);
      toast("Scheme saved to your account.");
    }
    await Promise.all([loadSchemes(), loadSavedSchemes()]);
  } catch (error) {
    toast(error.message, true);
  }
}

async function trackScheme(scheme) {
  if (!state.user) {
    openAuth("login");
    toast("Log in to keep your application tracker private and persistent.");
    return;
  }
  try {
    await api("/applications", { method: "POST", body: { scheme_id: scheme.id } });
    toast("Added to your application tracker.");
    await loadApplications();
  } catch (error) {
    toast(error.message, true);
  }
}

function schemeCard(scheme, matchResult = null) {
  const card = node("article", "scheme-card");
  const top = node("div", "scheme-card-top");
  top.append(node("span", "category-label", humanize(scheme.category || "scheme")));
  if (matchResult) top.append(eligibilityBadge(matchResult.status));
  else top.append(node("span", "scope-label", scheme.state || "Central"));
  card.append(top);

  const title = node("h3", "scheme-card-title", scheme.name || scheme.id);
  card.append(title);
  card.append(node("p", "scheme-card-copy", scheme.description || "Open the scheme record for details."));
  const verificationLabel = scheme.verification_status === "VERIFIED_FROM_OFFICIAL_SOURCE"
    ? "Official details verified"
    : scheme.verification_status === "SOURCE_UNAVAILABLE"
      ? "Official source unavailable at last check"
      : "Details need official review";
  card.append(node("p", "verification-status", verificationLabel));
  if (scheme.government_level || scheme.department) {
    const meta = [humanize(scheme.government_level), scheme.department].filter(Boolean).join(" · ");
    card.append(node("p", "scheme-card-meta", meta));
  }
  const actions = node("div", "scheme-card-actions");
  actions.append(button("View details", "text-button", () => showSchemeDetails(scheme)));
  const saveLabel = state.bookmarks.has(scheme.id) ? "Saved ✓" : "Save +";
  actions.append(button(saveLabel, "save-button", () => toggleBookmark(scheme), `${saveLabel} ${scheme.name}`));
  actions.append(button("Track ↗", "track-button", () => trackScheme(scheme), `Track ${scheme.name}`));
  card.append(actions);
  if (matchResult && Array.isArray(matchResult.missing_info) && matchResult.missing_info.length) {
    card.append(node("p", "match-hint", `To check further: ${matchResult.missing_info.map(humanize).join(", ")}`));
  }
  return card;
}

function buildCategoryFilters(categories) {
  const container = $("category-pills");
  container.replaceChildren();
  const values = ["", ...categories];
  for (const category of values) {
    const label = category || "All schemes";
    const pill = button(label, "category-pill", () => {
      state.category = category;
      state.page = 1;
      updateCategorySelection();
      loadSchemes();
    });
    pill.dataset.category = category;
    container.append(pill);
  }
}

function updateCategorySelection() {
  document.querySelectorAll(".category-pill").forEach((pill) => {
    const selected = pill.dataset.category === state.category;
    pill.classList.toggle("is-selected", selected);
    pill.setAttribute("aria-pressed", String(selected));
  });
}

async function loadSchemes() {
  const message = $("directory-message");
  const grid = $("scheme-grid");
  message.textContent = "Loading the current scheme catalogue…";
  grid.replaceChildren();
  const params = new URLSearchParams({
    page: String(state.page),
    page_size: String(PAGE_SIZE),
  });
  if (state.search) params.set("q", state.search);
  if (state.category) params.set("category", state.category);
  if (state.governmentState) params.set("state", state.governmentState);
  try {
    const data = await api(`/schemes?${params}`);
    const schemes = data.items || [];
    state.totalPages = Math.max(1, data.pages || 1);
    message.textContent = `${data.total} scheme${data.total === 1 ? "" : "s"} in the current catalogue`;
    if (!schemes.length) {
      grid.append(node("p", "empty-state", "No schemes match these filters. Try a broader search."));
    } else {
      schemes.forEach((scheme) => grid.append(schemeCard(scheme)));
    }
    renderPagination(data.page || 1, state.totalPages);
  } catch (error) {
    message.textContent = error.message;
    grid.append(node("p", "error-state", "The scheme directory could not be loaded."));
  }
}

function renderPagination(page, totalPages) {
  const pagination = $("pagination");
  pagination.replaceChildren();
  pagination.hidden = totalPages <= 1;
  if (totalPages <= 1) return;
  const previous = button("← Previous", "page-button", () => {
    state.page = Math.max(1, page - 1);
    loadSchemes();
  });
  previous.disabled = page <= 1;
  pagination.append(previous);
  pagination.append(node("span", "page-current", `Page ${page} of ${totalPages}`));
  const next = button("Next →", "page-button", () => {
    state.page = Math.min(totalPages, page + 1);
    loadSchemes();
  });
  next.disabled = page >= totalPages;
  pagination.append(next);
}

async function loadCategories() {
  try {
    const categories = await api("/categories");
    buildCategoryFilters(categories);
    updateCategorySelection();
  } catch (error) {
    $("directory-message").textContent = error.message;
  }
}

function fillStateFilter(schemes) {
  const filter = $("state-filter");
  const current = filter.value;
  const states = [...new Set(schemes.map((scheme) => scheme.state).filter(Boolean))].sort();
  filter.replaceChildren(new Option("All states", ""), new Option("Central schemes", "Central"));
  states.forEach((value) => filter.add(new Option(value, value)));
  if ([...filter.options].some((option) => option.value === current)) filter.value = current;
}

async function initStateFilter() {
  try {
    fillStateFilter(await api("/schemes"));
  } catch (error) {
    $("directory-message").textContent = error.message;
  }
}

function addReasons(container, heading, entries, failed = false) {
  if (!Array.isArray(entries) || !entries.length) return;
  const section = node("div", failed ? "reason-block reason-failed" : "reason-block");
  section.append(node("h4", "", heading));
  const list = node("ul", "");
  entries.forEach((entry) => {
    const text = entry.reason || entry;
    list.append(node("li", "", text));
  });
  section.append(list);
  container.append(section);
}

function renderMatchResult(result) {
  const scheme = result.scheme || { id: result.scheme_id, name: result.name };
  const card = schemeCard(scheme, result);
  const reasons = node("div", "match-reasons");
  addReasons(reasons, "What appears to match", result.matched);
  addReasons(reasons, "What does not match", result.failed, true);
  if (reasons.childElementCount) card.append(reasons);
  if (result.manual_review) card.append(node("p", "verification-note", "Some eligibility details still need confirmation from the official source."));
  return card;
}

function renderFollowUpQuestions(results) {
  const questions = results.flatMap((result) =>
    (result.unknown_conditions || []).map((condition) => ({
      ...condition,
      scheme: result.name,
    }))
  );
  const unique = [...new Map(questions.map((question) => [question.id, question])).values()];
  if (!unique.length) return null;
  const section = node("section", "follow-up-panel");
  section.append(node("h3", "", "A few details could improve this match"));
  section.append(node("p", "muted-copy", "Your answers are self-reported and do not replace official verification."));
  const fields = node("div", "follow-up-fields");
  unique.forEach((question) => {
    const label = node("label", "follow-up-question", question.question);
    const select = node("select", "");
    select.setAttribute("aria-label", question.question);
    select.append(new Option("Choose an answer", ""));
    select.append(new Option("Yes", "true"));
    select.append(new Option("No", "false"));
    if (typeof state.specialAnswers[question.id] === "boolean") {
      select.value = String(state.specialAnswers[question.id]);
    }
    select.addEventListener("change", () => {
      if (select.value !== "") state.specialAnswers[question.id] = select.value === "true";
    });
    label.append(select);
    fields.append(label);
  });
  section.append(fields);
  section.append(button("Recheck these answers", "button button-outline", () => runMatch()));
  return section;
}

function renderMatchResults(data) {
  const container = $("match-results");
  container.replaceChildren();
  const results = data.results || [];
  if (!results.length) {
    container.append(node("p", "empty-state", "No matches found. Add more profile details and try again."));
    return;
  }
  container.append(node("p", "match-summary", "These are discovery leads, not a decision on your eligibility."));
  const followUps = renderFollowUpQuestions(results);
  if (followUps) container.append(followUps);

  const groups = [
    ["likely_eligible", "Potential matches"],
    ["possibly_eligible", "More information needed"],
  ];
  groups.forEach(([status, title]) => {
    const matching = results.filter((result) => result.status === status);
    if (!matching.length) return;
    const section = node("section", "match-group");
    section.append(node("h3", "", title));
    const grid = node("div", "scheme-grid match-grid");
    matching.forEach((result) => grid.append(renderMatchResult(result)));
    section.append(grid);
    container.append(section);
  });
  const unmatched = results.filter((result) => result.status === "not_matched");
  if (unmatched.length) {
    const details = node("details", "unmatched-details");
    details.append(node("summary", "", `Not matched from the available details (${unmatched.length})`));
    const grid = node("div", "scheme-grid match-grid");
    unmatched.forEach((result) => grid.append(renderMatchResult(result)));
    details.append(grid);
    container.append(details);
  }
  container.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runMatch() {
  const description = $("situation").value.trim();
  if (!description) {
    toast("Describe your situation before searching.", true);
    $("situation").focus();
    return;
  }
  const fields = getProfileFields();
  const payload = { description, ...fields };
  if (Object.keys(state.specialAnswers).length) payload.special_answers = state.specialAnswers;
  state.lastMatch = payload;
  const submit = $("match-submit");
  submit.disabled = true;
  submit.textContent = "Checking the catalogue…";
  $("match-results").replaceChildren(node("p", "loading-note", "Comparing your answers with the current scheme criteria…"));
  try {
    if (state.user) {
      state.profile = (await api("/profile", { method: "PUT", body: fields })).profile;
    }
    const data = await api("/match", { method: "POST", body: payload });
    renderMatchResults(data);
    renderAccount();
  } catch (error) {
    $("match-results").replaceChildren(node("p", "error-state", error.message));
  } finally {
    submit.disabled = false;
    submit.innerHTML = 'Find relevant schemes <span aria-hidden="true">↗</span>';
  }
}

async function loadSavedSchemes() {
  const container = $("saved-schemes");
  container.replaceChildren();
  if (!state.user) {
    $("saved-count").textContent = "—";
    container.append(node("p", "empty-note", "Log in to keep a personal list of schemes."));
    return;
  }
  try {
    const bookmarks = await api("/bookmarks");
    state.bookmarks = new Set(bookmarks.map((item) => item.scheme_id));
    $("saved-count").textContent = String(bookmarks.length);
    if (!bookmarks.length) {
      container.append(node("p", "empty-note", "Your saved schemes will appear here."));
      return;
    }
    const schemes = await Promise.all(
      bookmarks.map((bookmark) => api(`/schemes/${encodeURIComponent(bookmark.scheme_id)}`))
    );
    schemes.forEach((scheme) => {
      const row = node("div", "saved-item");
      row.append(button(scheme.name, "saved-name", () => showSchemeDetails(scheme)));
      row.append(button("Remove", "remove-button", () => toggleBookmark(scheme)));
      container.append(row);
    });
  } catch (error) {
    container.append(node("p", "error-state", error.message));
  }
}

async function saveApplication(appId, changes, quiet = false) {
  try {
    const updated = await api(`/applications/${encodeURIComponent(appId)}`, {
      method: "PATCH",
      body: changes,
    });
    if (!quiet) toast("Tracker updated.");
    return updated;
  } catch (error) {
    toast(error.message, true);
    await loadApplications();
    return null;
  }
}

function renderApplication(row) {
  const card = node("article", "application-card");
  const heading = node("div", "application-heading");
  heading.append(node("h4", "", row.scheme_name || row.scheme_id));
  const status = node("select", "application-status");
  status.setAttribute("aria-label", `Application status for ${row.scheme_name || row.scheme_id}`);
  ["Not started", "In progress", "Submitted", "Approved", "Rejected"].forEach((value) => {
    status.add(new Option(value, value, false, value === row.status));
  });
  status.addEventListener("change", async () => {
    const updated = await saveApplication(row.id, { status: status.value }, true);
    if (updated) row.status = updated.status;
  });
  heading.append(status);
  card.append(heading);

  const documents = Array.isArray(row.documents) ? row.documents : [];
  if (documents.length) {
    const list = node("ul", "document-checklist");
    documents.forEach((document, index) => {
      const item = node("li", "");
      const checkbox = node("input", "");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(document.checked);
      checkbox.id = `application-${row.id}-doc-${index}`;
      checkbox.addEventListener("change", async () => {
        const updatedList = documents.map((entry, itemIndex) => ({
          ...entry,
          checked: itemIndex === index ? checkbox.checked : Boolean(entry.checked),
        }));
        const updated = await saveApplication(row.id, { documents: updatedList }, true);
        if (updated) row.documents = updated.documents;
      });
      const label = node("label", "", document.name);
      label.htmlFor = checkbox.id;
      item.append(checkbox, label);
      list.append(item);
    });
    card.append(node("p", "checklist-title", "Document checklist"));
    card.append(list);
  } else {
    card.append(node("p", "empty-note", "No document checklist is recorded for this scheme."));
  }

  const controls = node("div", "tracker-controls");
  const deadlineLabel = node("label", "tracker-field", "Deadline");
  const deadline = node("input", "");
  deadline.type = "date";
  deadline.value = row.deadline || "";
  deadline.addEventListener("change", async () => {
    await saveApplication(row.id, { deadline: deadline.value || null }, true);
    await loadReminders();
  });
  deadlineLabel.append(deadline);
  const notesLabel = node("label", "tracker-field", "Your notes");
  const notes = node("textarea", "");
  notes.rows = 2;
  notes.maxLength = 2000;
  notes.value = row.notes || "";
  notes.addEventListener("blur", async () => {
    if (notes.value !== (row.notes || "")) {
      const updated = await saveApplication(row.id, { notes: notes.value });
      if (updated) row.notes = updated.notes;
    }
  });
  notesLabel.append(notes);
  controls.append(deadlineLabel, notesLabel);
  card.append(controls);
  card.append(button("Remove from tracker", "remove-button", async () => {
    if (!window.confirm(`Remove "${row.scheme_name || row.scheme_id}" from your tracker?`)) return;
    try {
      await api(`/applications/${encodeURIComponent(row.id)}`, { method: "DELETE" });
      toast("Removed from your tracker.");
      await Promise.all([loadApplications(), loadReminders()]);
    } catch (error) {
      toast(error.message, true);
    }
  }));
  return card;
}

async function loadApplications() {
  const container = $("applications");
  container.replaceChildren();
  try {
    const rows = await api("/applications");
    $("application-count").textContent = String(rows.length);
    if (!rows.length) {
      container.append(node("p", "empty-note", state.user
        ? "Track a scheme to organise your next steps."
        : "Log in to build a private application tracker."));
      return;
    }
    rows.forEach((row) => container.append(renderApplication(row)));
  } catch (error) {
    $("application-count").textContent = "—";
    container.append(node("p", "error-state", error.message));
  }
}

async function loadReminders() {
  const container = $("reminders");
  container.replaceChildren();
  try {
    const rows = await api("/reminders");
    rows.forEach((row) => {
      const item = node("p", "reminder-item");
      item.append(
        node("strong", "", row.scheme_name || row.scheme_id),
        node("span", "", `Deadline ${row.deadline}`)
      );
      container.append(item);
    });
    if (!rows.length) container.append(node("p", "empty-note", "No upcoming or overdue deadlines."));
  } catch (error) {
    container.append(node("p", "error-state", error.message));
  }
}

async function loadWorkspace() {
  state.bookmarks.clear();
  await Promise.all([loadSavedSchemes(), loadApplications(), loadReminders()]);
  await loadSchemes();
}

async function handleAuthSubmit(form, endpoint) {
  const payload = Object.fromEntries(new FormData(form).entries());
  const message = $("auth-message");
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  message.textContent = endpoint.endsWith("register") ? "Creating your account…" : "Signing you in…";
  try {
    await api(endpoint, { method: "POST", body: payload });
    form.reset();
    dialog("auth-dialog").close();
    toast(endpoint.endsWith("register") ? "Your account is ready." : "You are signed in.");
    await loadAccount();
    if (state.lastMatch) {
      await runMatch();
    }
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

function configureSpeech(buttonId, onTranscript) {
  const trigger = $(buttonId);
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    trigger.hidden = true;
    if (buttonId === "profile-mic") $("voice-note").textContent = "Voice input is not supported in this browser.";
    return;
  }
  trigger.addEventListener("click", () => {
    const recognition = new Recognition();
    recognition.lang = $("voice-language").value;
    recognition.interimResults = false;
    recognition.continuous = false;
    trigger.disabled = true;
    trigger.textContent = "Listening…";
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0] && result[0].transcript)
        .filter(Boolean)
        .join(" ")
        .trim();
      if (transcript) onTranscript(transcript);
    };
    recognition.onerror = (event) => {
      toast(`Voice input error: ${event.error}. You can type instead.`, true);
    };
    recognition.onend = () => {
      trigger.disabled = false;
      trigger.textContent = buttonId === "profile-mic" ? "Speak" : "⌁";
      trigger.setAttribute("aria-label", buttonId === "profile-mic" ? "Describe your situation by voice" : "Search by voice");
    };
    try {
      recognition.start();
    } catch {
      trigger.disabled = false;
      trigger.textContent = buttonId === "profile-mic" ? "Speak" : "⌁";
      toast("Voice input could not start. Please type instead.", true);
    }
  });
}

function debounce(callback, delay) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => callback(...args), delay);
  };
}

function configureEvents() {
  $("login-open").addEventListener("click", () => openAuth("login"));
  $("logout-button").addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
      state.user = null;
      state.profile = {};
      state.bookmarks.clear();
      renderAccount();
      await loadWorkspace();
      toast("You are logged out.");
    } catch (error) {
      toast(error.message, true);
    }
  });

  document.querySelectorAll("[data-dialog-close]").forEach((closeButton) => {
    closeButton.addEventListener("click", () => closeButton.closest("dialog").close());
  });
  document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
    tab.addEventListener("click", () => switchAuthMode(tab.dataset.authMode));
  });
  for (const id of ["auth-dialog", "scheme-dialog"]) {
    dialog(id).addEventListener("click", (event) => {
      if (event.target === dialog(id)) dialog(id).close();
    });
  }

  $("login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    handleAuthSubmit(event.currentTarget, "/auth/login");
  });
  $("register-form").addEventListener("submit", (event) => {
    event.preventDefault();
    handleAuthSubmit(event.currentTarget, "/auth/register");
  });
  $("match-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.specialAnswers = {};
    runMatch();
  });
  $("scheme-search").addEventListener("input", debounce(() => {
    state.search = $("scheme-search").value.trim();
    state.page = 1;
    loadSchemes();
  }, 220));
  $("search-clear").addEventListener("click", () => {
    $("scheme-search").value = "";
    state.search = "";
    state.page = 1;
    loadSchemes();
  });
  $("state-filter").addEventListener("change", () => {
    state.governmentState = $("state-filter").value;
    state.page = 1;
    loadSchemes();
  });
  $("profile-mic").addEventListener("keydown", (event) => {
    if (event.key === " ") event.preventDefault();
  });
  configureSpeech("search-mic", (transcript) => {
    $("scheme-search").value = transcript;
    $("scheme-search").dispatchEvent(new Event("input", { bubbles: true }));
  });
  configureSpeech("profile-mic", (transcript) => {
    const current = $("situation").value.trim();
    $("situation").value = current ? `${current} ${transcript}` : transcript;
    runMatch();
  });
}

async function initialize() {
  configureEvents();
  await Promise.all([loadCategories(), initStateFilter(), loadSchemes()]);
  await loadAccount();
}

initialize();
