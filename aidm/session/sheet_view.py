"""The character sheet on the wire (SPEC 8, 12): `request_sheet` -> `sheet`.

Only the asking player's own hero is sent (a downed hero too: the sheet shows death saves).
The derived sheet comes from `rules.sheet.build_sheet` (never stored), and `level_up` carries
`rules.level_options.level_up_options` while the hero can level up, so the level-up dialog can
offer exactly the picks `rules.leveling.validate_level_up` will accept.

Public API: `send_sheet`.
"""

from aidm.models.protocol_server import ErrorCode, SheetMsg
from aidm.rules.level_options import level_up_options
from aidm.rules.sheet import build_sheet
from aidm.session.table_core import Player, TableCore


def send_sheet(core: TableCore, player: Player) -> None:
    creature = core.state.creatures.get(player.creature_id or "")
    if creature is None or creature.pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You do not have a hero yet.")
        return
    chars = core.regs.combat.chars
    msg = SheetMsg(
        creature_id=creature.id,
        sheet=build_sheet(creature, chars),
        level_up=level_up_options(creature, chars),
    )
    core.send(player.id, msg)
