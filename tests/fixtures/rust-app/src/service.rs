//! Authentication, such as it is.

use crate::store::{Cache, Describe, UserStore};

/// Compares a stored record with a submitted password.
pub fn verify(record: &str, password: &str) -> bool {
    record.ends_with(password)
}

/// Authenticates a user, returning their display name.
pub fn authenticate(user_id: &str, password: &str) -> Option<String> {
    let store = UserStore::new("users.json");
    let record = store.get(user_id)?;
    let names: Vec<String> = record.split(':').map(|part| part.to_string()).collect();
    if verify(&record, password) {
        return names.first().cloned();
    }
    None
}

/// Describes one particular store, which is a resolvable call.
pub fn describe_store(store: &UserStore) -> String {
    store.describe()
}

/// Describes whatever it is handed, which is not.
pub fn describe_any(item: &dyn Describe) -> String {
    item.describe()
}

/// Never called by anything in this crate.
pub fn unused_helper(cache: &Cache) -> Option<String> {
    cache.get("nobody")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verifies_a_matching_password() {
        assert!(verify("ada:secret", "secret"));
    }
}
