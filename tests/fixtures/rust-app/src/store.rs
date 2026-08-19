//! Storage, and the two things in this crate that can describe themselves.

use std::collections::HashMap;

/// Anything that can say what it is, for the log.
pub trait Describe {
    fn describe(&self) -> String;
}

/// An in-memory cache of parsed records.
pub struct Cache {
    entries: HashMap<String, String>,
}

/// A user record store backed by a file.
pub struct UserStore {
    path: String,
    cache: Cache,
}

impl Cache {
    /// Returns a cached record, if there is one.
    pub fn get(&self, key: &str) -> Option<String> {
        self.entries.get(key).cloned()
    }
}

impl UserStore {
    /// Opens a store over the given path.
    pub fn new(path: &str) -> UserStore {
        UserStore {
            path: path.to_string(),
            cache: Cache { entries: HashMap::new() },
        }
    }

    /// Returns the record for a user id, cache first.
    pub fn get(&self, user_id: &str) -> Option<String> {
        if let Some(hit) = self.cache.get(user_id) {
            return Some(hit);
        }
        let raw = self.read();
        raw.get(user_id).cloned()
    }

    /// Returns the shorter of two borrowed records.
    pub fn shorter<'a>(&self, left: &'a str, right: &'a str) -> &'a str {
        if left.len() <= right.len() {
            left
        } else {
            right
        }
    }

    /* A comment with an unbalanced brace { and a /* nested */ comment in it. */
    fn read(&self) -> HashMap<String, String> {
        HashMap::new()
    }
}

impl Describe for UserStore {
    fn describe(&self) -> String {
        format!("store at {}", self.path)
    }
}

impl Describe for Cache {
    fn describe(&self) -> String {
        String::from("cache")
    }
}
