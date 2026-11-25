#include "../src/widget.h"

int main(void) {
    struct Widget widget = {0, "sample"};
    char buffer[32];
    return widget_render(&widget, buffer, sizeof buffer);
}
