import type { Scope } from "../api/types";

// States the fact only; category names are never hard-coded here.
export default function ScopeRibbon({ scope }: { scope: Scope }) {
  return (
    <div className={`ribbon ${scope.restricted ? "scoped" : "open-acc"}`}>
      <span className="lk" aria-hidden="true">
        {scope.restricted ? "\u{1F512}" : "\u{1F513}"}
      </span>
      <span>
        {scope.restricted ? (
          <>
            <b>Answered from evidence inside your role&rsquo;s scope.</b> Retrieval was filtered server-side, before the model.
          </>
        ) : (
          <>
            <b>Unrestricted.</b> Answered from evidence across all categories.
          </>
        )}
      </span>
    </div>
  );
}
