import express from "express";
import { UserService } from "../services/userService";

const app = express();
const service = new UserService();

/** GET /api/users/:id */
export async function getUser(req, res) {
  const user = await service.load(req.params.id);
  res.json(user);
}

app.get("/api/users/:id", getUser);

/** Boot the HTTP server. */
export function main() {
  app.listen(3000);
}
