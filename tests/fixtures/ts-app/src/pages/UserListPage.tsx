import React, { useEffect, useState } from "react";
import { UserCard } from "../components/UserCard";
import { useUsers } from "../hooks/useUsers";

/** The page that lists every user. */
export function UserListPage() {
  const { users, reload } = useUsers();
  useEffect(() => {
    reload();
  }, []);
  return (
    <main>
      {users.map((u) => (
        <UserCard key={u.id} user={u} onSelect={reload} />
      ))}
    </main>
  );
}
