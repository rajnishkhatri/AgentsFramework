"use client";

import { useEffect, useState } from "react";

/**
 * UserList — a component that calls a cloud API directly from the browser.
 *
 * FD7 critical (FE-AP anti-pattern): a React component must not call a cloud
 * service directly. It also hardcodes a bearer credential in the client bundle,
 * leaking a live secret to every visitor. All cloud access must go through the
 * BFF/middleware (Frontend Ring).
 */
export function UserList() {
  const [users, setUsers] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    fetch("https://api.example.com/users", {
      headers: { Authorization: "Bearer sk-live-1234567890" },
    })
      .then((r) => r.json())
      .then(setUsers);
  }, []);

  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{u.name}</li>
      ))}
    </ul>
  );
}
