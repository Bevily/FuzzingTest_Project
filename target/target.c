#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

int main() {
    char buf[100];
    memset(buf, 0, 100); // 确保干净

    // 强制读取固定长度，或者读到 EOF
    ssize_t n = read(0, buf, 100);
    if (n <= 0) return 1;

    // 【关键】把读到的内容打印到标准错误，方便我们看
    fprintf(stderr, "[C-DEBUG] Received %ld bytes: [%s]\n", n, buf);

    if (buf[0] == 'c') {
        fprintf(stderr, "[C-DEBUG] Hit Branch 1 (c)\n");
        if (buf[1] == 'r') {
            fprintf(stderr, "[C-DEBUG] Hit Branch 2 (r)\n");
            if (buf[2] == 'a' && buf[3] == 's' && buf[4] == 'h') {
                fprintf(stderr, "[C-DEBUG] Hit Crash Branch!\n");
                abort();
            }
        }
    }
    return 0;
}