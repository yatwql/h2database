"""Engine that drives widgets."""

from pkg.widget import Widget


class Engine:
    """Drives widgets through a pipeline."""

    def run(self, widget: Widget) -> None:
        """Run one widget."""
        widget.describe()


def count() -> int:
    """Number of engines available."""
    return 1
