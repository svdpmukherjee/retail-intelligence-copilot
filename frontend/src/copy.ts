// Authored UI copy. Degradation sentences are chosen from field presence in the
// response (sql_error, grounding.path, grounding.issues), never from response text.
export const SQL_DEGRADED =
  "The data query failed, so metrics and trends are hidden. The text below comes from other evidence.";
export const NO_EVIDENCE =
  "No supporting evidence was found for this question within your access scope. Try rephrasing or asking about a different topic.";
export const FALLBACK_NOTE =
  "Shown as a verbatim extract from the sources because the written answer could not be fully verified.";

export const STAGES = ["routing", "retrieving (scoped)", "grounding", "answer"];

export const TAGLINE = "Ask about reviews, products and policy. Every answer is grounded and cited.";

const STARTERS: Record<string, string[]> = {
  support: ["What is the return policy?", "What do customers complain about most?"],
  marketing: ["What do customers praise most about our products?", "Which products have the best ratings?"],
  executive: ["Summarise overall customer sentiment.", "Which products have the highest revenue?"],
};
const DEFAULT_STARTERS = ["What can you tell me about customer reviews?", "Summarise our return policy."];

export function startersFor(role: string): string[] {
  return STARTERS[role] ?? DEFAULT_STARTERS;
}

export type EvidenceType = "sql" | "review" | "policy/doc";

// UI-derived tag (handoff Pending #3): no backend source_type field.
export function evidenceType(sourceId: string, label: string): EvidenceType {
  if (sourceId === "sql") return "sql";
  return label.toLowerCase().startsWith("review") ? "review" : "policy/doc";
}
