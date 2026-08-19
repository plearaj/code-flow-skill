import React from "react";
import { formatName } from "@app/services/userService";

/** One user, rendered as a card. */
export function UserCard({ user, onSelect }) {
  const label = formatName(user);
  return (
    <div className="card" onClick={() => onSelect(user.id)}>
      {label}
    </div>
  );
}
