import type {
  AssistantTurn,
  FeedbackDetail,
  Overview,
  Session,
  SurveyAnswers,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string | null;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Participant API -------------------------------------------------------
export const api = {
  startSession: (
    recruitment_source = "direct",
    external_ref = "",
    condition?: number,
    newsletter?: string,
  ) =>
    request<Session>("/api/session/start/", {
      method: "POST",
      body: {
        recruitment_source,
        external_ref,
        ...(condition ? { condition } : {}),
        ...(newsletter ? { newsletter } : {}),
      },
    }),

  getSession: (publicId: string) =>
    request<Session>(`/api/session/${publicId}/`),

  consent: (publicId: string) =>
    request<Session>(`/api/session/${publicId}/consent/`, { method: "POST" }),

  submitInitial: (publicId: string, initial_text: string) =>
    request<AssistantTurn>(`/api/session/${publicId}/feedback/initial/`, {
      method: "POST",
      body: { initial_text },
    }),

  // Condition 3: one more round of the feedback-assistant conversation.
  chatTurn: (publicId: string, message: string) =>
    request<AssistantTurn>(`/api/session/${publicId}/feedback/chat/`, {
      method: "POST",
      body: { message },
    }),

  // Condition 3: consolidate the conversation into one submission-ready draft.
  finalDraft: (publicId: string) =>
    request<{ draft: string; used_llm: boolean }>(
      `/api/session/${publicId}/feedback/final-draft/`,
      { method: "POST" },
    ),

  submitFinal: (
    publicId: string,
    final_text: string,
    time_on_task_seconds: number,
    revision_count: number,
  ) =>
    request<{ status: string }>(`/api/session/${publicId}/feedback/final/`, {
      method: "POST",
      body: { final_text, time_on_task_seconds, revision_count },
    }),

  submitSurvey: (publicId: string, answers: SurveyAnswers) =>
    request<{ status: string }>(`/api/session/${publicId}/survey/`, {
      method: "POST",
      body: answers,
    }),

  // --- Researcher API ------------------------------------------------------
  login: (username: string, password: string) =>
    request<{ access: string; refresh: string }>("/api/auth/token/", {
      method: "POST",
      body: { username, password },
    }),

  overview: (token: string) =>
    request<Overview>("/api/research/overview/", { token }),

  responses: (
    token: string,
    params: { condition?: string; unrated?: boolean; page?: number } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.condition) q.set("condition", params.condition);
    if (params.unrated) q.set("unrated", "1");
    if (params.page) q.set("page", String(params.page));
    const qs = q.toString();
    return request<{
      count: number;
      next: string | null;
      previous: string | null;
      results: FeedbackDetail[];
    }>(`/api/research/responses/${qs ? `?${qs}` : ""}`, { token });
  },

  createRating: (
    token: string,
    feedbackId: number,
    body: Record<string, unknown>,
  ) =>
    request(`/api/research/responses/${feedbackId}/ratings/`, {
      method: "POST",
      token,
      body,
    }),

  exportUrl: () => `${API_BASE}/api/research/export.csv`,

  // --- Prompt playground ---------------------------------------------------
  promptLabDefault: (token: string) =>
    request<{ system_prompt: string }>("/api/research/prompt-lab/default/", {
      token,
    }),

  promptLabSamples: (
    token: string,
    source: "collected" | "study" = "collected",
    limit = 30,
  ) =>
    request<{ source: string; samples: string[] }>(
      `/api/research/prompt-lab/samples/?source=${source}&limit=${limit}`,
      { token },
    ),

  promptLabRun: (token: string, system_prompt: string, samples: string[]) =>
    request<{
      count: number;
      provider: string;
      model: string;
      results: { sample: string; response: string; ok: boolean; error?: string }[];
    }>("/api/research/prompt-lab/run/", {
      method: "POST",
      token,
      body: { system_prompt, samples },
    }),

  promptLabStatus: (token: string) =>
    request<{
      provider: string;
      model: string;
      ok: boolean;
      error: string | null;
      has_key: boolean;
      configured: Record<string, boolean>;
    }>("/api/research/prompt-lab/status/", { token }),
};

export { ApiError };
