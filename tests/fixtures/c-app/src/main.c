#include "store.h"

#include <stdio.h>

/** Looks one hard-coded user up and prints the record. */
int main(void) {
    char buffer[64];
    store_init();
    if (store_find("ada", buffer, sizeof(buffer))) {
        printf("%s\n", buffer);
    }
    return 0;
}
