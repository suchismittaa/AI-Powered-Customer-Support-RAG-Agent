// api.js — thin client around the existing FastAPI backend (api.py)

const API_BASE = ""; // same-origin; api.py serves both API and this frontend

function getToken() {
  return localStorage.getItem("supportai_token");
}
export function setSession(session) {
  localStorage.setItem("supportai_token", session.token);
  localStorage.setItem("supportai_user", JSON.stringify({
    user_id: session.user_id, name: session.name, email: session.email,
    role: session.role, org_id: session.org_id,
  }));
}
export function clearSession() {
  localStorage.removeItem("supportai_token");
  localStorage.removeItem("supportai_user");
}
export function getUser() {
  const raw = localStorage.getItem("supportai_user");
  return raw ? JSON.parse(raw) : null;
}
export function isAuthed() {
  return !!getToken();
}

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!isForm && body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : (isForm ? body : JSON.stringify(body)),
  });

  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),

  ask: (query, use_cache = true) => request("/ask", { method: "POST", body: { query, use_cache } }),
  health: () => request("/health"),
  systemStatus: () => request("/system/status"),

  conversations: (limit = 50) => request(`/conversations?limit=${limit}`),
  clearConversations: () => request("/conversations", { method: "DELETE" }),
  feedback: (query, answer, rating) => request("/feedback", { method: "POST", body: { query, answer, rating } }),

  ticketsList: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    return request(`/tickets${qs.toString() ? "?" + qs.toString() : ""}`);
  },
  ticketsKpis: () => request("/tickets/kpis"),
  ticketSuggest: (query, triage_reason) =>
    request(`/tickets/suggest?query=${encodeURIComponent(query)}&triage_reason=${encodeURIComponent(triage_reason || "")}`),
  createTicket: (payload) => request("/tickets", { method: "POST", body: payload }),
  getTicket: (id) => request(`/tickets/${id}`),
  updateTicketStatus: (id, status) => request(`/tickets/${id}`, { method: "PATCH", body: { status } }),

  kbDocuments: () => request("/kb/documents"),
  kbHealth: () => request("/kb/health"),
  kbUpload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/kb/upload", { method: "POST", body: form, isForm: true });
  },
  kbIngest: () => request("/kb/ingest", { method: "POST" }),
  kbIngestStatus: () => request("/kb/ingest/status"),

  analyticsOverview: () => request("/analytics/overview"),
  analyticsTrend: (days = 14) => request(`/analytics/resolution-trend?days=${days}`),
  analyticsCategories: () => request("/analytics/categories"),
  analyticsEscalation: () => request("/analytics/escalation-reasons"),
  analyticsCache: () => request("/analytics/cache"),

  evalHistory: () => request("/eval/history"),
  evalDetail: (runId) => request(`/eval/history/${runId}`),
  evalRun: () => request("/eval/run", { method: "POST" }),
};
