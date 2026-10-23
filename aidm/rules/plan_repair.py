"""Plan repairs after assembly (M29.7c, round-2 playtests R11, R10, R1). Pure.

The campaign model writes quests by names; these repairs run on the assembled plan, so a bad
model plan never reaches play (repair over reject, each repair a `quest_repair` note):
- one item per name and place (R11): an `obtain` step whose item looks like (`same_item`) an
  item an earlier step of the act already places at one of its places takes that item's exact
  name, so the engine places ONE copy (`aidm.rules.quest_items` skips a copy an earlier step
  already lies there) and every quest that needs it counts it (`aidm.rules.quest_steps`). Order:
  the act's main routes, then its side quests in plan order. A shared item is handed to ONE
  person: a later `deliver` of it to someone else becomes a `meet` with that person ("Show the
  <item> to <name>"), so no hand-over can strand another route (DECISIONS M29.7c);
- a reward is never the quest's own item (R10): a `reward_item` with the words of an item a step
  of that quest obtains or delivers becomes "<giver>'s Token" (Favour, Keepsake... when taken;
  secrets revealed by showing the old reward follow the new name);
- a `clear` step's text names the place and what it fields (R1): the model's text promised deeds
  and creatures the place never had ("Snuff the bone-pyre the acolytes are stoking" at a copse of
  stirges and goblins), so it becomes "Win the fight at <place> (<foes>)"; at a gateway the foe
  is the master.

Public API: `repair_plan(plan, notes) -> CampaignPlan` (notes appended to `notes`).
"""

from dataclasses import dataclass, field

from aidm.data.srd import srd
from aidm.models.campaign import (
    Act,
    CampaignPlan,
    NodePlan,
    NpcPlan,
    QuestPlan,
    RegionPlan,
    SecretPlan,
)
from aidm.models.problem import Problem
from aidm.models.quests import MainQuestPlan, QuestStep, StepKind
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.quest_items import item_words, same_item
from aidm.rules.quest_plan import short_text
from aidm.rules.secrets import item_key

MAX_REWARD_ITEM = 60
TOKENS = ("Token", "Favour", "Keepsake", "Thanks")
SHOW = "Show the {item} to {npc}"
CLEAR = "Win the fight at {place} ({foes})"


def _note(owner: str, message: str) -> Problem:
    return Problem(code="quest_repair", message=f"{owner}: {message}", subject=owner)


@dataclass
class _Owner:
    """One step list of an act: a main route or a side quest (`label` for the notes)."""

    label: str
    steps: list[QuestStep]


@dataclass
class _Canon:
    name: str
    nodes: frozenset[str]
    owners: set[int] = field(default_factory=set[int])


def _names(plan: CampaignPlan) -> dict[str, str]:
    names = {n.id: n.name for n in plan.npcs}
    return names | {boss_npc_id(r): r.boss.name for r in plan.all_regions()}


def _owners(plan: CampaignPlan, act: Act) -> list[_Owner]:
    routes = act.main.routes if act.main is not None else ()
    owners = [_Owner(f"{main_quest_id(act.region)}/{r.id}", list(r.steps)) for r in routes]
    return owners + [_Owner(q.id, list(q.steps)) for q in plan.quests if q.act == act.index]


def _canon(canons: list[_Canon], step: QuestStep) -> _Canon | None:
    here = frozenset(step.nodes)
    return next((c for c in canons if c.nodes & here and same_item(c.name, step.item or "")), None)


def _share_names(owners: list[_Owner], notes: list[Problem]) -> list[_Canon]:
    """Lookalike items at one place take the first one's name; the canons held by 2+ owners."""
    canons: list[_Canon] = []
    for i, owner in enumerate(owners):
        renamed: dict[str, str] = {}
        for j, step in enumerate(owner.steps):
            if step.kind is StepKind.DELIVER and step.item in renamed:
                owner.steps[j] = step.model_copy(update={"item": renamed[step.item]})
            if step.kind is not StepKind.OBTAIN or not step.item:
                continue
            found = _canon(canons, step)
            if found is None:
                canons.append(_Canon(step.item, frozenset(step.nodes), {i}))
                continue
            if i not in found.owners:
                msg = (
                    f"the {found.name!r} is one item, shared with {owners[min(found.owners)].label}"
                )
                notes.append(_note(owner.label, msg))
            found.owners.add(i)
            if step.item != found.name:
                renamed[step.item] = found.name
                owner.steps[j] = step.model_copy(update={"item": found.name})
                notes.append(_note(owner.label, f"{step.item!r} is the {found.name!r}: one item"))
    return [c for c in canons if len(c.owners) > 1]


def _one_recipient(
    owners: list[_Owner], shared: list[_Canon], names: dict[str, str], notes: list[Problem]
) -> None:
    keys = {item_key(c.name) for c in shared}
    first: dict[str, str] = {}
    for owner in owners:
        for j, step in enumerate(owner.steps):
            key = item_key(step.item or "")
            if step.kind is not StepKind.DELIVER or key not in keys or step.npc is None:
                continue
            to = first.setdefault(key, step.npc)
            if to == step.npc:
                continue
            npc = names.get(step.npc, step.npc)
            text = short_text(SHOW.format(item=step.item, npc=npc))
            owner.steps[j] = QuestStep(kind=StepKind.MEET, text=text, npc=step.npc)
            msg = f"the {step.item!r} goes to {names.get(to, to)}; {npc} is only shown it"
            notes.append(_note(owner.label, msg))


def _act_with(act: Act, quests: dict[str, QuestPlan], owners: list[_Owner]) -> Act:
    by_label = {o.label: o.steps for o in owners}
    if act.main is not None:
        prefix = main_quest_id(act.region)
        routes = tuple(
            r.model_copy(update={"steps": tuple(by_label[f"{prefix}/{r.id}"])})
            for r in act.main.routes
        )
        act = act.model_copy(update={"main": MainQuestPlan(routes=routes)})
    for quest in [q for q in quests.values() if q.act == act.index]:
        quests[quest.id] = quest.model_copy(update={"steps": tuple(by_label[quest.id])})
    return act


def _shared_items(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    names = _names(plan)
    quests = {q.id: q for q in plan.quests}
    acts: list[Act] = []
    for act in plan.acts:
        owners = _owners(plan, act)
        _one_recipient(owners, _share_names(owners, notes), names, notes)
        acts.append(_act_with(act, quests, owners))
    return plan.model_copy(update={"acts": tuple(acts), "quests": tuple(quests.values())})


def _own_items(quest: QuestPlan) -> list[str]:
    return [s.item for s in quest.steps if s.item and s.kind in (StepKind.OBTAIN, StepKind.DELIVER)]


def _token(plan: CampaignPlan, quest: QuestPlan, taken: set[str]) -> str:
    """A fresh reward named after the giver: "<giver>'s Token" (then Favour, Keepsake...)."""
    giver = _names(plan).get(quest.giver_npc_id, quest.giver_npc_id)
    names = [short_text(f"{giver}'s {noun}", MAX_REWARD_ITEM) for noun in TOKENS]
    name = next((n for n in names if item_key(n) not in taken), f"{names[0]} {len(taken)}")
    taken.add(item_key(name))
    return name


def _fit_rewards(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    taken = {item_key(q.reward_item) for q in plan.quests if q.reward_item}
    renamed: dict[str, str] = {}
    quests: list[QuestPlan] = []
    for quest in plan.quests:
        old = quest.reward_item
        if old and any(item_words(old) == item_words(i) for i in _own_items(quest)):
            new = _token(plan, quest, taken)
            renamed[old] = new
            notes.append(_note(quest.id, f"the reward {old!r} is the quest's own item; {new!r}"))
            quest = quest.model_copy(update={"reward_item": new})
        quests.append(quest)
    if not renamed:
        return plan
    npcs = tuple(_renamed_reveals(npc, renamed) for npc in plan.npcs)
    return plan.model_copy(update={"quests": tuple(quests), "npcs": npcs})


def _renamed_reveals(npc: NpcPlan, renamed: dict[str, str]) -> NpcPlan:
    """`npc` with its secrets revealed by showing a renamed reward following the new name."""
    secrets: list[SecretPlan] = []
    for secret in npc.secrets:
        new = renamed.get(secret.reveal.item or "")
        if new is not None:
            reveal = secret.reveal.model_copy(update={"item": new})
            secret = secret.model_copy(update={"reveal": reveal})
        secrets.append(secret)
    return npc.model_copy(update={"secrets": tuple(secrets)})


def _foes(region: RegionPlan, node: NodePlan) -> str:
    if node.id == region.gateway.id:
        return region.boss.name
    monsters = srd().monsters
    found = (monsters.find(m) for m in node.encounter_themes)
    return ", ".join(m.name.lower() for m in found if m is not None) or "its dangers"


def _clear_text(region: RegionPlan, step: QuestStep) -> QuestStep:
    node = next((n for n in region.nodes() if n.id == step.nodes[0]), None)
    if node is None:
        return step
    text = short_text(CLEAR.format(place=node.name, foes=_foes(region, node)))
    return step.model_copy(update={"text": text})


def _clear_texts(plan: CampaignPlan) -> CampaignPlan:
    def fixed(region: RegionPlan, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        return tuple(_clear_text(region, s) if s.kind is StepKind.CLEAR else s for s in steps)

    acts: list[Act] = []
    for act in plan.acts:
        if act.main is not None:
            routes = tuple(
                r.model_copy(update={"steps": fixed(act.region, r.steps)}) for r in act.main.routes
            )
            act = act.model_copy(update={"main": MainQuestPlan(routes=routes)})
        acts.append(act)
    regions = {a.index: a.region for a in plan.acts}
    quests = tuple(
        q.model_copy(update={"steps": fixed(regions[q.act], q.steps)}) for q in plan.quests
    )
    return plan.model_copy(update={"acts": tuple(acts), "quests": quests})


def repair_plan(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    repaired = _clear_texts(_fit_rewards(_shared_items(plan, notes), notes))
    return CampaignPlan.model_validate(repaired.model_dump())
