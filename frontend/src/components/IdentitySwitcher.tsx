import { IDENTITIES, Identity, identityLabel } from "../identities";

interface Props {
  identity: Identity;
  onIdentity: (identity: Identity) => void;
  selectRef: React.Ref<HTMLSelectElement>;
}

// Demo scaffolding, not product: the tag is text (not colour-only) and the card is dashed.
export default function IdentitySwitcher({ identity, onIdentity, selectRef }: Props) {
  return (
    <div className="demo">
      <span className="demolabel">&#9881; demo &mdash; not a login</span>
      <select
        id="identity-select"
        className="user"
        aria-label="Demo identity — not a login"
        ref={selectRef}
        value={identity.userId}
        onChange={(e) => {
          const next = IDENTITIES.find((i) => i.userId === e.target.value);
          if (next) onIdentity(next);
        }}
      >
        {IDENTITIES.map((i) => (
          <option key={i.userId} value={i.userId}>
            {identityLabel(i)}
          </option>
        ))}
      </select>
      <div className="idnote">
        A demo control so a reviewer can see who sees what. No password, no account &mdash; not part of what a retail
        user uses.
      </div>
    </div>
  );
}
