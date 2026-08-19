#include "store.h"

#include <string.h>

static const char *RECORDS = "ada:secret";

/** Reads one record out of the fixed table. */
static const char *read_record(const char *user_id) {
    if (strncmp(RECORDS, user_id, strlen(user_id)) == 0) {
        return RECORDS;
    }
    return NULL;
}

void store_init(void) {
    /* Nothing to do: the table is static. { an unbalanced brace, in a comment */
}

int store_find(const char *user_id, char *out, size_t out_len) {
    const char *record = read_record(user_id);
    if (record == NULL) {
        return 0;
    }
    strncpy(out, record, out_len);
    return 1;
}
