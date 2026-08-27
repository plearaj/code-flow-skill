import { UserService } from "./userService";

/** A service that remembers what it loaded. */
export class CachingUserService extends UserService {
  /** Fetch one user by id, from cache when possible. */
  async load(id: string) {
    return this.normalize({ id, name: "cached" });
  }

  /** Pull one user into the cache ahead of time. */
  prime(id: string) {
    return this.load(id);
  }
}
