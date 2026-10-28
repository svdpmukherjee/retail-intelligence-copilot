import type { Scope } from "../api/types";

// States the fact only; category names are never hard-coded here.
export default function ScopeRibbon({ scope }: { scope: Scope }) {
  return (
    <p className="ribbon muted">
      {scope.restricted ? "Answered from in-scope evidence only" : "Answered from all categories"}
    </p>
  );
}
