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
}

export interface AnswerResult {
  answer: string;
  citations: Citation[];
  audit: Record<string, unknown>;
}

export interface QueryResponse extends AnswerResult {
  thread_id: string | null;
  user_id: string | null;
}
