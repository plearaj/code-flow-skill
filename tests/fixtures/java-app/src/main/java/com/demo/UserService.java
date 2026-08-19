package com.demo;

import java.util.Optional;

/** Authenticates users against the store. */
public class UserService implements Describable {

    private final UserStore store;

    /** Wires the service to a store. */
    public UserService(UserStore store) {
        this.store = store;
    }

    /** Authenticates a user, returning their record. */
    public Optional<String> authenticate(String userId, String password) {
        Optional<String> record = store.find(userId);
        if (record.isPresent() && verify(record.get(), password)) {
            return record;
        }
        return Optional.empty();
    }

    /** Compares a stored record with a submitted password. */
    private boolean verify(String record, String password) {
        return record.endsWith(password);
    }

    /** Compares a stored record with a salted password. */
    private boolean verify(String record, String password, String salt) {
        return record.endsWith(password + salt);
    }

    @Override
    public String describe() {
        return "user service";
    }

    /** Nothing in this repository calls this. */
    public void unusedHelper() {
        store.find("nobody");
    }
}
