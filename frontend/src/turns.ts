import type { QueryResponse } from "./api/types";

// live: this session's response, held in memory with its audit and citations.
// restored: stored redacted text only (GET /threads/{id}); no audit or citations exist for it.
export type Turn =
  | { kind: "live"; id: string; query: string; res: QueryResponse }
  | { kind: "restored"; id: string; roleKind: "user" | "assistant"; content: string; threadRole: string };
