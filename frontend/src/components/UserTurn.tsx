export default function UserTurn({ query }: { query: string }) {
  return (
    <div className="turn turn-user">
      <p>{query}</p>
    </div>
  );
}
