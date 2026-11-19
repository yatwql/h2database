package org.example.core;

import org.example.Widget;

/**
 * Drives widgets through a simple pipeline.
 */
public class Engine {
    public void run(Widget widget) {
        widget.describe();
    }

    public int count() {
        return 1;
    }
}
