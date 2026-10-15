"""Id schemes of the world entities a campaign plan makes (pure, one place for each scheme).

Public API: `boss_npc_id(region) -> str` (the boss registered as a world NPC at its gateway,
M5.3), `main_quest_id(region) -> str` (the act's main quest in `World.quests`, M23).
"""

from aidm.models.campaign import RegionPlan


def boss_npc_id(region: RegionPlan) -> str:
    return f"boss-{region.id}"


def main_quest_id(region: RegionPlan) -> str:
    return f"main-{region.id}"
