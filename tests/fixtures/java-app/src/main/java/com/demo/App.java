package com.demo;

/** Command-line entry point for the demo. */
public class App {

    /** Authenticates one hard-coded user and prints the outcome. */
    public static void main(String[] args) {
        UserService service = new UserService(new UserStore());
        System.out.println(service.authenticate("ada", "ada:secret"));
    }
}
