// Authored UI copy. Degradation sentences are chosen from field presence in the
// response (sql_error, grounding.path, grounding.issues), never from response text.
export const SQL_DEGRADED =
  "We couldn't calculate the numbers for this one — here's what customers actually said:";
export const NO_EVIDENCE =
  "I couldn't find anything about that in the sources you have access to. Try rephrasing, or ask about a different product or topic.";
export const FALLBACK_NOTE =
  "Here are the exact words from the sources:";

export const SYSTEM_ERROR = "Something went wrong getting that answer. Please try again in a moment.";

export const TAGLINE = "Every answer comes with the exact sources it\u2019s based on \u2014 nothing made up.";
export const LOADING = "Looking through the sources\u2026";
export const SCOPE_UNKNOWN = "Answers only draw on the sources you have access to.";

// Plain reassurance wording derived from audit.scope; categories are never hard-coded
// and a missing scope never widens into "all categories".
export function scopeLine(scope: { restricted: boolean; categories: string[] } | null): string {
  if (!scope) return SCOPE_UNKNOWN;
  if (!scope.restricted) return "You can see all categories.";
  const names = scope.categories.map((c) => c.replace(/_/g, " "));
  if (names.length === 0) return SCOPE_UNKNOWN;
  return `You can see: ${names.join(", ")}`;
}

const STARTERS: Record<string, string[]> = {
  support: ["What is the return policy?", "What do customers complain about most?"],
  marketing: ["What do customers praise most about our products?", "Which products have the best ratings?"],
  executive: ["Summarise overall customer sentiment.", "Which products have the highest revenue?"],
};
const DEFAULT_STARTERS = ["What can you tell me about customer reviews?", "Summarise our return policy."];

export function startersFor(role: string): string[] {
  return STARTERS[role] ?? DEFAULT_STARTERS;
}

export const HISTORICAL_NOTE = "historical turn — reasoning & evidence not stored for replay";
