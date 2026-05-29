const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type RequestOptions = RequestInit & { auth?: boolean };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);

  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (options.auth !== false) {
    const token = typeof window !== "undefined" ? localStorage.getItem("opsflow_token") : null;
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>("/auth/me"),
  workspace: () => request<Workspace>("/workspaces/demo"),
  systemStatus: () => request<SystemStatus>("/system/status"),
  resetDemo: () =>
    request<{ status: string; message: string }>("/demo/reset", {
      method: "POST",
    }),

  metrics: () => request<Metrics>("/metrics"),
  jobs: () => request<IngestionJob[]>("/jobs"),
  connectors: () => request<Connector[]>("/connectors"),
  workItems: () => request<WorkItem[]>("/workitems"),
  actions: () => request<SuggestedAction[]>("/actions"),
  actionDetail: (id: string) => request<SuggestedActionDetail>(`/actions/${id}`),
  audit: () => request<AuditLog[]>("/audit"),

  searchWorkItems: (q: string, limit = 8) =>
    request<SearchResult[]>(
      `/search/work-items?q=${encodeURIComponent(q)}&limit=${limit}`
    ),

  similarWorkItems: (id: string, limit = 5) =>
    request<SearchResult[]>(`/workitems/${id}/similar?limit=${limit}`),

  generateActions: () =>
    request<{ generated_actions: number }>("/actions/generate", {
      method: "POST",
    }),

  approveAction: (id: string) =>
    request<SuggestedAction>(`/actions/${id}/approve`, {
      method: "POST",
    }),

  rejectAction: (id: string) =>
    request<SuggestedAction>(`/actions/${id}/reject`, {
      method: "POST",
    }),

  uploadCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);

    return request<{ job_id: string; status: string; row_count: number }>(
      "/sources/upload_csv",
      {
        method: "POST",
        body: form,
      }
    );
  },
};

export type User = {
  id: string;
  email: string;
  full_name: string;
};

export type Workspace = {
  id: string;
  name: string;
};

export type SystemStatus = {
  api: string;
  database: string;
  redis: string;
  ai_provider: string;
  ai_description: string;
};

export type Metrics = {
  total_work_items: number;
  pending_actions: number;
  approved_actions: number;
  rejected_actions: number;
  approval_rate: number;
  estimated_minutes_saved: number;
  failed_actions: number;
  high_risk_items: number;
  completed_jobs: number;
  queued_jobs: number;
};

export type WorkItem = {
  id: string;
  title: string;
  body: string;
  customer?: string | null;
  channel: string;
  priority: string;
  status: string;
  category?: string | null;
  risk_score: number;
  created_at: string;
};

export type SearchResult = {
  work_item: WorkItem;
  similarity: number;
  matched_content: string;
  reason: string;
};

export type SuggestedAction = {
  id: string;
  work_item_id: string;
  action_type: string;
  title: string;
  payload: Record<string, unknown>;
  explanation: string;
  confidence: number;
  status: string;
  created_at: string;
  reviewed_at?: string | null;
};

export type SuggestedActionDetail = SuggestedAction & {
  work_item: WorkItem;
  evidence: { source: string; content: string; reason: string }[];
  simulated_integrations: Record<string, unknown>[];
};

export type AuditLog = {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id?: string | null;
  description: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type IngestionJob = {
  id: string;
  filename: string;
  source_type: string;
  status: string;
  row_count: number;
  inserted_work_items: number;
  generated_actions: number;
  error_message?: string | null;
  created_at: string;
  processed_at?: string | null;
};

export type Connector = {
  id: string;
  name: string;
  provider: string;
  status: string;
  description: string;
  last_sync: string;
  records: number;
};
