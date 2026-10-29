import type { QueryRequest, QueryResponse, ThreadDetail, ThreadListItem } from "./types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail !== undefined) detail = JSON.stringify(body.detail);
    } catch {
      // non-JSON error body: keep the status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function getRoles(): Promise<string[]> {
  const body = await request<{ roles: string[] }>("/roles");
  return body.roles;
}

export function postQuery(req: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
}

export async function getThreads(userId: string, role: string): Promise<ThreadListItem[]> {
  const body = await request<{ threads: ThreadListItem[] }>(
    `/threads?user_id=${encodeURIComponent(userId)}&role=${encodeURIComponent(role)}`,
  );
  return body.threads;
}

export function getThread(id: string, userId: string): Promise<ThreadDetail> {
  return request<ThreadDetail>(
    `/threads/${encodeURIComponent(id)}?user_id=${encodeURIComponent(userId)}`,
  );
}
