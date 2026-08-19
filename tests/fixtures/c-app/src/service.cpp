#include "service.hpp"
#include "store.h"

#include <utility>

namespace demo {

UserService::UserService(std::string table) : table_(std::move(table)), calls_(0) {}

std::string UserService::authenticate(const std::string &user_id) {
    char buffer[128];
    calls_ += 1;
    if (store_find(user_id.c_str(), buffer, sizeof(buffer))) {
        return std::string(buffer);
    }
    return describe();
}

std::string UserService::describe() const {
    return "user service for " + table_;
}

}  // namespace demo
