//! The HTTP surface.

use crate::service::authenticate;

/// Handles a request for one user.
#[get("/users/{id}")]
pub async fn show_user(id: String) -> String {
    match authenticate(&id, "") {
        Some(name) => name,
        None => String::from("unknown"),
    }
}
