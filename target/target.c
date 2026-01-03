#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

int main() {
    char buf[100];
    if (read(0, buf, 100) > 0) {
        if (buf[0] == 'c' && buf[1] == 'r' && buf[2] == 'a' && buf[3] == 's' && buf[4] == 'h') {
            // 触发崩溃
            int *p = NULL;
            *p = 123;
        }
        printf("Received: %s\n", buf);
    }
    return 0;
}