import type {
  AssistantTurn,
  BlindFeedback,
  FeedbackDetail,
  Overview,
  Session,
  SurveyAnswers,
  UserInfo,
} from "./types";
import {
  clearToken,
  getRefreshToken,
  saveToken,
} from "./auth";

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

let refreshRequest: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  if (!refreshRequest) {
    refreshRequest = fetch(`${API_BASE}/api/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const data = (await response.json()) as { access: string };
        saveToken(data.access);
        return data.access;
      })
      .catch(() => null)
      .finally(() => {
        refreshRequest = null;
      });
  }
  return refreshRequest;
}

async function request<T>(
  path: string,
  opts: RequestOptions = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (res.status === 401 && opts.token && !retried) {
    const access = await refreshAccessToken();
    if (access) return request<T>(path, { ...opts, token: access }, true);
    clearToken();
    if (typeof window !== "undefined") {
      window.location.assign("/researcher/login?expired=1");
    }
  }
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
    request<{ draft: string }>(
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

  me: (token: string) =>
    request<UserInfo>("/api/auth/me/", { token }),

  raters: (token: string) =>
    request<UserInfo[]>("/api/auth/raters/", { token }),

  createRater: (
    token: string,
    body: { username: string; email: string; password: string },
  ) =>
    request<UserInfo>("/api/auth/raters/", {
      method: "POST",
      token,
      body,
    }),

  updateRater: (
    token: string,
    id: number,
    body: { email?: string; is_active?: boolean; password?: string },
  ) =>
    request<UserInfo>(`/api/auth/raters/${id}/`, {
      method: "PATCH",
      token,
      body,
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

  ratingQueue: (token: string, page = 1) =>
    request<{
      count: number;
      next: string | null;
      previous: string | null;
      results: BlindFeedback[];
    }>(`/api/research/responses/?unrated=1&page=${page}`, { token }),

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

  responseDetail: (token: string, feedbackId: number) =>
    request<FeedbackDetail>(`/api/research/responses/${feedbackId}/`, { token }),

  exportUrl: () => `${API_BASE}/api/research/export.csv`,
};

export { ApiError };
