package org.example;

/**
 * A tiny widget with a name.
 */
public class Widget {
    private final String name;

    public Widget(String name) {
        this.name = name;
    }

    public String describe() {
        return "widget:" + name;
    }

    public int size() {
        return name.length();
    }
}
