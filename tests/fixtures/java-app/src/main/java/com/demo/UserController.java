package com.demo;

/** HTTP surface for user lookups. */
@RestController
public class UserController {

    private final UserService service;

    /** Wires the controller to the service. */
    public UserController(UserService service) {
        this.service = service;
    }

    /** Handles a request for one user. */
    @GetMapping("/users/{id}")
    public String show(String id) {
        return service.authenticate(id, "").orElse("unknown");
    }
}
