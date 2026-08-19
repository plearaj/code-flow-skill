/** Talks to the user API. */
export class UserService {
  private cache = new Map();

  /** Fetch one user by id. */
  async load(id: string) {
    const response = await fetch(`/api/users/${id}`);
    return this.normalize(await response.json());
  }

  normalize(raw: any) {
    return { id: raw.id, name: raw.name };
  }
}

/** Format a display name. Not called from anywhere. */
export function formatName(user: { name: string }) {
  return user.name.trim();
}
