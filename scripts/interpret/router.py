"""The old router's reading of a line on a state (the baseline; goes with the router at M36.10).

`reading(state, actor_id, text, scope)`: the fight rows' reading in a fight, the explore
precheck out of one. Returns `(found, label)`: the intent object (or None) and a plain
serialisation for the candidate file. When the router modules are gone, the reading is
unavailable (`UNAVAILABLE`) and the baseline is skipped.
"""

import dataclasses
import json
from typing import Any

from pydantic import BaseModel

from aidm.models.action_menu import MenuScope
from aidm.models.state import GameState

UNAVAILABLE = "router_unavailable"


def plain(obj: object) -> Any:
    if isinstance(obj, BaseModel):
        return {"type": type(obj).__name__, **obj.model_dump(mode="json")}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {"type": type(obj).__name__, **dataclasses.asdict(obj)}
    if isinstance(obj, list | tuple):
        items: list[Any] = list(obj)
        return [plain(item) for item in items]
    if isinstance(obj, str | int | float | bool) or obj is None:
        return obj
    return repr(obj)


def reading(
    state: GameState, actor_id: str, text: str, scope: MenuScope
) -> tuple[object | None, Any]:
    try:
        if scope in (MenuScope.FIGHT, MenuScope.OFF_TURN):
            from aidm.dm.intent_router import fight_intent

            found = fight_intent(state, actor_id, text)
        else:
            from aidm.dm.precheck import precheck

            found = precheck(state, actor_id, text)
    except ImportError:
        return None, UNAVAILABLE
    except Exception as exc:  # the baseline must never stop a measurement run
        return None, f"router_error:{type(exc).__name__}"
    return found, json.loads(json.dumps(plain(found), default=repr))
