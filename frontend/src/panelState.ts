import { ApiError } from "./api/client";
import type { QueryResponse } from "./api/types";

// Handoff §2: exactly one of these is active at a time.
export type PanelState =
  | "empty"
  | "loading"
  | "grounded"
  | "fallback"
  | "degraded-SQL"
  | "no-evidence"
  | "error-400"
  | "error-502";

export interface PanelInputs {
  inFlight: boolean;
  response: QueryResponse | null;
  error: unknown;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

// ApiError.message carries the backend `detail` string.
export function derivePanelState({ inFlight, response, error }: PanelInputs): PanelState {
  if (inFlight) return "loading";
  if (error) return error instanceof ApiError && error.status === 400 ? "error-400" : "error-502";
  if (!response) return "empty";
  const { audit, citations } = response;
  if (audit.sql_error) return "degraded-SQL";
  if (audit.grounding.path === "none" || citations.length === 0) return "no-evidence";
  if (audit.grounding.issues.length > 0) return "fallback";
  return "grounded";
}
