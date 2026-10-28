export default function UserTurn({ query }: { query: string }) {
  return (
    <div className="turn user">
      <div className="av" aria-hidden="true">
        You
      </div>
      <div className="body">{query}</div>
    </div>
  );
}
