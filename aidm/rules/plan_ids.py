"""Id schemes of the world entities a campaign plan makes (pure, one place for each scheme).

Public API: `boss_npc_id(region) -> str` (the boss registered as a world NPC at its gateway,
M5.3), `main_quest_id(region) -> str` (the act's main quest in `World.quests`, M23),
`quest_item_id(quest_id, route_id, step, copy) -> str` (copy `copy` of the item an `obtain`
step places: a `WorldItem` id, then the `Keepsake` id once picked up, M23.3).
"""

from aidm.models.campaign import RegionPlan


def boss_npc_id(region: RegionPlan) -> str:
    return f"boss-{region.id}"


def main_quest_id(region: RegionPlan) -> str:
    return f"main-{region.id}"


def quest_item_id(quest_id: str, route_id: str | None, step: int, copy: int) -> str:
    return f"qi-{quest_id}-{route_id or 'own'}-{step}-{copy}"
