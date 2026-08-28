#pragma once

#include <string>

namespace demo {

/// Anything that can say what it is, for the log.
class Describable {
public:
    /// Returns a human-readable description.
    virtual std::string describe() const { return "thing"; }
};

}  // namespace demo
