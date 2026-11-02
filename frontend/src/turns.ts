import type { QueryResponse } from "./api/types";

// live: this session's response, held in memory with its audit and citations.
// restored: a turn reopened from history. When the assistant turn has a stored render snapshot,
// `res` carries it and the turn replays in full (charts + evidence); otherwise only the redacted
// `content` text survives (older turns saved before snapshots existed).
export type Turn =
  | { kind: "live"; id: string; query: string; res: QueryResponse }
  | {
      kind: "restored";
      id: string;
      roleKind: "user" | "assistant";
      content: string;
      threadRole: string;
      res?: QueryResponse;
    };
