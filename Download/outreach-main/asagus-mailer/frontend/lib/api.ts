import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ── Senders ──────────────────────────────────────────────────────────────────
export const sendersApi = {
  list: () => API.get("/api/senders"),
  create: (data: any) => API.post("/api/senders", data),
  update: (id: number, data: any) => API.put(`/api/senders/${id}`, data),
  delete: (id: number) => API.delete(`/api/senders/${id}`),
  test: (id: number, passwords?: { smtp_password?: string; imap_password?: string }) =>
    API.post(`/api/senders/${id}/test`, passwords || {}),
  stats: (id: number) => API.get(`/api/senders/${id}/stats`),
  startWarmup: (id: number) => API.post(`/api/senders/${id}/warmup/start`),
  stopWarmup: (id: number) => API.post(`/api/senders/${id}/warmup/stop`),
  sentBox: (id: number, limit = 50) => API.get(`/api/senders/${id}/sent-box`, { params: { limit } }),
  preset: (provider: string) => API.get(`/api/senders/presets/${provider}`),
};

// ── Leads ─────────────────────────────────────────────────────────────────────
export const leadsApi = {
  listFiles: () => API.get("/api/leads/files"),
  uploadCsv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return API.post("/api/leads/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  confirmUpload: (params: {
    temp_filename: string; original_name: string;
    email_col: string; name_col?: string;
    business_col?: string; phone_col?: string;
  }) => API.post("/api/leads/confirm-upload", null, { params }),
  getFileLeads: (fileId: number, page = 1, pageSize = 20, status?: string) =>
    API.get(`/api/leads/files/${fileId}`, { params: { page, page_size: pageSize, status } }),
  getFileStats: (fileId: number) => API.get(`/api/leads/files/${fileId}/stats`),
  deleteFile: (fileId: number) => API.delete(`/api/leads/files/${fileId}`),
  getLead: (leadId: number) => API.get(`/api/leads/${leadId}`),
  globalSent: (page = 1) => API.get("/api/leads/global-sent", { params: { page } }),
};

// ── Templates ─────────────────────────────────────────────────────────────────
export const templatesApi = {
  list: (type?: string) => API.get("/api/templates", { params: type ? { template_type: type } : {} }),
  create: (params: { name: string; template_type: string; subject_variants: string[]; body: string; ab_test_enabled: boolean }) =>
    API.post("/api/templates", null, { params: { ...params, subject_variants: JSON.stringify(params.subject_variants) } }),
  update: (id: number, params: any) =>
    API.put(`/api/templates/${id}`, null, {
      params: params.subject_variants ? { ...params, subject_variants: JSON.stringify(params.subject_variants) } : params,
    }),
  delete: (id: number) => API.delete(`/api/templates/${id}`),
  preview: (id: number) => API.post(`/api/templates/${id}/preview`),
  spamCheck: (id: number) => API.post(`/api/templates/${id}/spam-check`),
};

// ── Campaigns ─────────────────────────────────────────────────────────────────
export const campaignsApi = {
  list: () => API.get("/api/campaigns"),
  create: (params: any) => API.post("/api/campaigns", null, {
    params: {
      ...params,
      initial_template_ids: JSON.stringify(params.initial_template_ids),
      sender_account_ids: JSON.stringify(params.sender_account_ids),
      followup_day3_template_ids: params.followup_day3_template_ids ? JSON.stringify(params.followup_day3_template_ids) : undefined,
      followup_day6_template_ids: params.followup_day6_template_ids ? JSON.stringify(params.followup_day6_template_ids) : undefined,
      sender_limits: params.sender_limits ? JSON.stringify(params.sender_limits) : undefined,
    },
  }),
  get: (id: number) => API.get(`/api/campaigns/${id}`),
  preview: (id: number) => API.get(`/api/campaigns/${id}/preview`),
  run: (id: number) => API.post(`/api/campaigns/${id}/run`),
  pause: (id: number) => API.post(`/api/campaigns/${id}/pause`),
  delete: (id: number) => API.delete(`/api/campaigns/${id}`),
  progress: (id: number) => API.get(`/api/campaigns/${id}/progress`),
  senderStats: (id: number) => API.get(`/api/campaigns/${id}/sender-stats`),
};

// ── Emails ────────────────────────────────────────────────────────────────────
export const emailsApi = {
  list: (params?: { campaign_id?: number; sender_id?: number; is_followup?: boolean; page?: number }) =>
    API.get("/api/emails", { params: { page_size: 20, ...params } }),
  get: (id: number) => API.get(`/api/emails/${id}`),
};

// ── Follow-ups ────────────────────────────────────────────────────────────────
export const followupsApi = {
  list: (params?: { followup_day?: number; status?: string; page?: number }) =>
    API.get("/api/followups", { params: { page_size: 20, ...params } }),
  stats: () => API.get("/api/followups/stats"),
  trigger: (id: number) => API.post(`/api/followups/${id}/trigger`),
  cancel: (id: number) => API.post(`/api/followups/${id}/cancel`),
};

// ── Replies ───────────────────────────────────────────────────────────────────
export const repliesApi = {
  list: (params?: { unread_only?: boolean; page?: number }) =>
    API.get("/api/replies", { params: { page_size: 20, ...params } }),
  stats: () => API.get("/api/replies/stats"),
  get: (id: number) => API.get(`/api/replies/${id}`),
  reply: (id: number, body: string) => API.post(`/api/replies/${id}/reply`, null, { params: { body } }),
  markRead: (id: number) => API.post(`/api/replies/${id}/read`),
  markUnsubscribe: (id: number) => API.post(`/api/replies/${id}/unsubscribe`),
  poll: () => API.post("/api/replies/poll"),
};

// ── Warmup ────────────────────────────────────────────────────────────────────
export const warmupApi = {
  sessions: () => API.get("/api/warmup/sessions"),
  session: (id: number) => API.get(`/api/warmup/sessions/${id}`),
  log: (page = 1) => API.get("/api/warmup/log", { params: { page } }),
};

// ── Analytics ─────────────────────────────────────────────────────────────────
export const analyticsApi = {
  overview: () => API.get("/api/analytics/overview"),
  campaigns: () => API.get("/api/analytics/campaigns"),
  templates: () => API.get("/api/analytics/templates"),
  abTest: () => API.get("/api/analytics/ab-test"),
  senders: () => API.get("/api/analytics/senders"),
  timeline: (days = 30) => API.get("/api/analytics/timeline", { params: { days } }),
  spamScores: () => API.get("/api/analytics/spam-scores"),
};

// ── Gmail Integration ───────────────────────────────────────────────────────
export const gmailIntegrationApi = {
  getConfig: () => API.get("/api/integrations/gmail"),
  setConfig: (payload: { client_id: string; client_secret?: string; redirect_uri?: string }) =>
    API.post("/api/integrations/gmail", payload),
  getAuthUrl: (senderId: number) =>
    API.get("/api/integrations/gmail/authorize", { params: { sender_id: senderId } }),
};

// ── Unsubscribes ──────────────────────────────────────────────────────────────
export const unsubscribesApi = {
  list: (page = 1) => API.get("/api/unsubscribes", { params: { page } }),
  add: (email: string) => API.post("/api/unsubscribes", null, { params: { email } }),
  remove: (id: number) => API.delete(`/api/unsubscribes/${id}`),
};

export default API;
