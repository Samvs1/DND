"""Narration tone shared by the narrator (dm) and the websocket protocol (SPEC 11).

Public API: `NarrationTone` (COMBAT / SOCIAL / EXPLORATION): the scene tone every narration
chunk carries; TTS speed and temperature follow it.
"""

from enum import StrEnum


class NarrationTone(StrEnum):
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"
