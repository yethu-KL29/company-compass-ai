import { KeyRound } from "lucide-react";

export function AdminAccess({
  token,
  onChange,
}: {
  token: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="admin-access panel">
      <label htmlFor="admin-token">
        <KeyRound size={15} />
        Admin token
      </label>
      <input
        id="admin-token"
        type="password"
        value={token}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Enter your admin token to make changes"
        autoComplete="off"
      />
      <p className="small muted">
        Published content is public. Adding or updating requires the admin
        token, held in memory for this session only.
      </p>
    </div>
  );
}
