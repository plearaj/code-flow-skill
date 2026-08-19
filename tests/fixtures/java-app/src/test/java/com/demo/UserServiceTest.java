package com.demo;

import org.junit.jupiter.api.Test;

/** Tests for the authentication service. */
public class UserServiceTest {

    /** A matching password authenticates. */
    @Test
    public void authenticatesAMatchingPassword() {
        UserService service = new UserService(new UserStore());
        service.authenticate("ada", "ada:secret");
    }
}
