/*
 * Copyright 2004-2025 H2 Group. Multiple-Licensed under the MPL 2.0,
 * and the EPL 1.0 (https://h2database.com/html/license.html).
 * Initial Developer: Alessandro Ventura
 */
package org.h2.security.auth;

/**
 * describe how to perform objects runtime configuration
 */
public interface Configurable {
    /**
     * configure the component
     * @param configProperties = configuration properties
     */
    void configure(ConfigProperties configProperties);
}
