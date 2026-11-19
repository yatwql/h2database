//! Example crate used by the language-analyzer tests.

use crate::core::Engine;

/// A tiny widget with a name.
pub struct Widget {
    name: String,
}

/// Build and run a widget.
pub fn build(name: String) -> Widget {
    let widget = Widget { name };
    Engine::run(&widget);
    widget
}
