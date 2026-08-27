#pragma once

#include <string>

namespace demo {

/// Anything that can say what it is, for the log.
class Describable {
public:
    /// Returns a human-readable description.
    virtual std::string describe() const { return "thing"; }
};

/// Authenticates users against the C store.
class UserService : public Describable {
public:
    /// Builds a service reading from the given table.
    explicit UserService(std::string table);

    /// Authenticates a user, returning their record.
    std::string authenticate(const std::string &user_id);

    /// Describes the service, for the log.
    std::string describe() const;

private:
    std::string table_;
    int calls_;
};

}  // namespace demo
