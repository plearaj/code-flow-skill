package com.demo;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/** An in-memory record store. */
public class UserStore implements Describable {

    /* A comment with an unbalanced brace { in it, and a quote " for good measure. */
    private static final String TEMPLATE = "{ \"id\": \"%s\" }";

    private final Map<String, String> records = new HashMap<>();

    /** Returns the record for a user id. */
    public Optional<String> find(String userId) {
        String hit = records.get(userId);
        return Optional.ofNullable(hit);
    }

    @Override
    public String describe() {
        return "user store";
    }
}
