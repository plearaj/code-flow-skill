package com.demo;

import java.util.List;

/** Builds the startup banner. */
public class Report {

    /** Describes everything it is handed, whatever it turns out to be. */
    public String describeAll(List<Describable> items) {
        StringBuilder out = new StringBuilder();
        for (Describable item : items) {
            out.append(item.describe());
        }
        return out.toString();
    }
}
