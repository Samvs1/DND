"""`ReducerError`: an event that cannot apply to the current state (always an engine bug).

Lives in its own module so the reducer parts (`reducer`, `encounter_apply`) share it without an
import cycle.
"""


class ReducerError(ValueError):
    """An event that cannot apply to the current state (an engine bug)."""
