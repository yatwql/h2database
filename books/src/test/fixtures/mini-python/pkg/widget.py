"""Widget helpers."""

from pkg.core.engine import Engine


class Widget:
    """A tiny widget with a name."""

    def __init__(self, name: str = "w") -> None:
        self.name = name

    def describe(self) -> str:
        """Return a human readable description."""
        return f"widget:{self.name}"


def build(name: str) -> Widget:
    """Build a widget and run the engine on it."""
    widget = Widget()
    Engine().run(widget)
    return widget
