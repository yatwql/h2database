/**
 * A widget that renders one row of the table.
 */
package com.example

import kotlinx.coroutines.launch

class Widget(private val name: String) {
    fun render(): String = name
}

fun helper(): Int = 1
