//! Demo binary for the Rust tracer fixture.

mod service;
mod store;
mod web;

use crate::service::authenticate;

/// Authenticates one hard-coded user and prints the outcome.
fn main() {
    let outcome = authenticate("ada", "secret");
    println!("{:?}", outcome);
}
