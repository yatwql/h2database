/* Widget implementation: the storage lives here, the API in the header. */
#include "widget.h"

#include <stdio.h>

static int widget_secret_counter = 0;

static void widget_note(void) {
    widget_secret_counter += 1;
}

int widget_render(const struct Widget *widget, char *out, ship_size_t size) {
    widget_note();
    return snprintf(out, size, "%d:%s", widget->id, widget->name);
}
