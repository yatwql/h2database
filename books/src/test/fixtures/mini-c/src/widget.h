/* Widget: the sample type this fixture exposes. */
#ifndef WIDGET_H
#define WIDGET_H

#include "../include/common.h"

struct Widget {
    int id;
    char name[16];
};

enum WidgetState {
    WIDGET_IDLE = 0,
    WIDGET_BUSY = 1,
};

typedef struct Widget Widget;

/* Render one widget into the caller's buffer. */
int widget_render(const struct Widget *widget, char *out, ship_size_t size);

#endif
