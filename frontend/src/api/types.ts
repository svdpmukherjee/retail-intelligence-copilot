// Mirrors backend/app/main.py (QueryRequest, QueryResponse) and backend/agents/composer.py.
export interface QueryRequest {
  query: string;
  role: string;
  thread_id?: string | null;
  user_id?: string | null;
}

export interface Citation {
  n: number;
  source_id: string; // chunk id, or "sql" for the SQL result
  label: string;
  snippet: string | null; // redacted source excerpt
}

export interface Grounding {
  path: "llm" | "extractive" | "none";
  issues: string[];
}

export interface Memory {
  thread_id: string;
  history_turns_used: number;
  persisted: number;
  error?: string;
}

export interface Scope {
  restricted: boolean;
  categories: string[];
}

export interface Audit {
  query: string;
  role: string;
  intent: "sql" | "review_rag" | "docs_rag" | "sql_rag";
  tool_path: string[];
  sources: string[];
  tokens: number;
  cost_usd: number;
  latency_ms: number;
  grounding: Grounding;
  sql_error?: string;
  memory?: Memory;
  scope: Scope;
}

export interface AnswerResult {
  answer: string;
  citations: Citation[];
  audit: Audit;
}

export interface QueryResponse extends AnswerResult {
  thread_id: string | null;
  user_id: string | null;
}
