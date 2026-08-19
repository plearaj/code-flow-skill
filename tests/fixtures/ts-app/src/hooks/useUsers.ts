import { useState } from "react";
import { UserService } from "../services/userService";

const service = new UserService();

/** Load and hold the user list. */
export function useUsers() {
  const [users, setUsers] = useState([]);
  const reload = async () => {
    const one = await service.load("1");
    setUsers([one]);
  };
  return { users, reload };
}
