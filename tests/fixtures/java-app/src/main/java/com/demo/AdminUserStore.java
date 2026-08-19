package com.demo;

import java.util.Optional;

/** A store that also serves administrators. */
public class AdminUserStore extends UserStore {

    /** Looks an administrator up through the ordinary store. */
    public Optional<String> findAdmin(String userId) {
        return find(userId);
    }
}
