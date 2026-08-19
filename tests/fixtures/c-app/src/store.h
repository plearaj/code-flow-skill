#ifndef DEMO_STORE_H
#define DEMO_STORE_H

#include <stddef.h>

/** Looks a user record up by id. Returns 1 when one was found. */
int store_find(const char *user_id, char *out, size_t out_len);

/** Prepares the store for use. */
void store_init(void);

#endif
