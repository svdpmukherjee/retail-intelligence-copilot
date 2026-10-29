import { IDENTITIES, Identity } from "../identities";

interface Props {
  identity: Identity;
  onIdentity: (identity: Identity) => void;
  selectRef: React.Ref<HTMLSelectElement>;
}

export default function IdentitySwitcher({ identity, onIdentity, selectRef }: Props) {
  return (
    <>
      <label htmlFor="identity-select">
        <h2>Demo identity</h2>
      </label>
      <span className="demolabel">&#9881; demo &mdash; not a login</span>
      <div className="idrow">
        <span className="k">role</span>
        <span className="v">{identity.role}</span>
      </div>
      <select
        id="identity-select"
        className="role"
        ref={selectRef}
        value={identity.userId}
        onChange={(e) => {
          const next = IDENTITIES.find((i) => i.userId === e.target.value);
          if (next) onIdentity(next);
        }}
      >
        {IDENTITIES.map((i) => (
          <option key={i.userId} value={i.userId}>
            {i.userId} &mdash; {i.role}
          </option>
        ))}
      </select>
      <div className="idnote">
        Switches the demo owner so owner-scoping is visible. No password, no session trust.
      </div>
    </>
  );
}
