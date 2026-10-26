"""The menu as the CHOOSE prompt shows it (M36.5): compact, one line per entry or per verb group.

Entries are written `id = label -> targets`, with `up to N` for a counted entry, `[spent]` when
its action is used and the entry's note. A verb with several entries that differ only by item
(`give:dagger`, `give:rope`, ... with the same targets) is ONE line: `give:<item> -> targets:
item, item (up to N), ...`, items that share a note grouped after it ("unequip it first:
dagger, shortbow"). When several groups list the same items, the items are written once (`ITEMS`)
and each group says `<item> = any of ITEMS` (or the few it leaves out). A target list that is
every listed target of its kinds is written "any foe" / "any place" and so on, unless a
target carries a note ("moves 30 ft first"); neighbouring targets with the same note share it
(M36.9). Grouping reads ids and fields only, never wording. Offer answers are never grouped
(M36.9 iteration 2: grouped, the model saw only `offer:<item>: fight, ..., parley:persuasion` and
none of what each answer does). Neighbouring entries whose labels differ only inside their
bracket share one line (`offer:parley:persuasion, offer:parley:deception = Parley ... (Persuasion:
...; Deception: ...)`). M38.4: a target note is written once: one the entry's own label already
says is dropped, and a long one an earlier entry wrote for the same target is "as for <entry>".
M40.4 (the round-7 fixtures put a cleric's full turn over the prompt bound): a spent single
entry is written without its targets (`id = label [spent]`: it cannot be done this turn), and
a long target list an earlier entry already wrote is "-> as for <that entry>".
M41.1 (round 7 Z4: "pays Wren 500 gold" with 60 carried was sent as 60, the "up to 60" read as
a cap): a gold entry (`menu_steps_scene.coin_entry`) is marked `qty: the sum said` instead.

Public API: `menu_lines(menu) -> list[str]`.
"""

from dataclasses import dataclass

from aidm.models.action_menu import ActionKind, ActionMenu, MenuEntry
from aidm.rules.menu_steps_scene import coin_entry

GROUP_MIN = 3
COIN_QTY = "qty: the sum said"  # M41.1: a gold entry's count is never capped at the purse
LONG_NOTE = 30
_KIND_WORDS = {
    "foe": "foe",
    "ally": "ally",
    "self": "you",
    "zone": "area",
    "person": "person",
    "place": "place",
    "thing": "thing",
}


@dataclass(frozen=True)
class _Group:
    verb: str
    entries: tuple[MenuEntry, ...]

    @property
    def items(self) -> tuple[str, ...]:
        return tuple(e.id.split(":", 1)[1] for e in self.entries)


def _verb(entry: MenuEntry) -> str | None:
    return entry.id.split(":", 1)[0] if ":" in entry.id else None


def _shape(entry: MenuEntry) -> tuple[object, ...]:
    return (entry.kind, entry.target_ids, entry.max_targets, entry.zone_ids, entry.spent)


def _groups(menu: ActionMenu) -> list[_Group]:
    """Entries of one verb and one shape (kind, targets, ...), at least GROUP_MIN of them."""
    by_key: dict[tuple[object, ...], list[MenuEntry]] = {}
    for entry in menu.entries:
        verb = _verb(entry)
        if verb is not None and not entry.target_notes and entry.kind is not ActionKind.OFFER:
            by_key.setdefault((verb, *_shape(entry)), []).append(entry)
    return [
        _Group(str(key[0]), tuple(entries))
        for key, entries in by_key.items()
        if len(entries) >= GROUP_MIN
    ]


def _targets(menu: ActionMenu, entry: MenuEntry) -> str:
    if not entry.target_ids:
        return ""
    labels = {t.id: t.label for t in menu.targets}
    kinds = {t.id: t.kind for t in menu.targets}
    notes = {
        t: n
        for t, n in entry.target_notes.items()
        if n not in labels.get(t, "") and n not in entry.label  # M38.4: said once
    }
    wanted = {kinds[t] for t in entry.target_ids}
    every = {t.id for t in menu.targets if t.kind in wanted}
    if not notes and every == set(entry.target_ids) and len(every) > 2:
        text = "any " + " or ".join(_KIND_WORDS[k] for k in sorted(wanted))
    else:
        text = _runs(entry.target_ids, notes)
    pick = f"pick up to {entry.max_targets} of: " if entry.max_targets > 1 else ""
    then = f"; then an area: {', '.join(entry.zone_ids)}" if entry.zone_ids else ""
    return f" -> {pick}{text}{then}"


def _runs(ids: tuple[str, ...], notes: dict[str, str]) -> str:
    """Targets in order; neighbours with the same note share it, written once after them, and
    runs are split by "; " (M36.9: "kobold-1, kobold-2 (moves 30 ft first, 60%); pc-p4")."""
    runs: list[tuple[str, list[str]]] = []
    for target in ids:
        note = notes.get(target, "")
        if runs and runs[-1][0] == note:
            runs[-1][1].append(target)
        else:
            runs.append((note, [target]))
    return "; ".join(", ".join(run) + (f" ({note})" if note else "") for note, run in runs)


def _extras(entry: MenuEntry) -> str:
    bits = [f"up to {entry.qty_max}"] if entry.qty_max > 1 else []
    if coin_entry(entry):  # M41.1 (round 7 Z4): a sum over the purse is the rules' to refuse
        bits = [COIN_QTY]
    if entry.spent:
        bits.append("spent")
    if entry.note:
        bits.append(entry.note)
    return f" [{'; '.join(bits)}]" if bits else ""


def _single(menu: ActionMenu, entry: MenuEntry, seen: dict[str, str]) -> str:
    # M40.4: a spent entry cannot be done this turn, so its targets are not written
    targets = "" if entry.spent else _targets(menu, entry)
    if len(targets) > LONG_NOTE:  # M40.4: a long target list an earlier entry wrote
        first = seen.setdefault(targets, entry.id)
        targets = targets if first == entry.id else f" -> as for {first}"
    return f"{entry.id} = {entry.label}{targets}{_extras(entry)}"


def _item_list(entries: tuple[MenuEntry, ...]) -> str:
    plain: list[str] = []
    noted: dict[str, list[str]] = {}
    for entry in entries:
        item = entry.id.split(":", 1)[1]
        word = f"{item} (up to {entry.qty_max})" if entry.qty_max > 1 else item
        if entry.note:
            noted.setdefault(entry.note, []).append(word)
        else:
            plain.append(word)
    parts = [", ".join(plain)] if plain else []
    parts += [f"{note}: {', '.join(words)}" for note, words in noted.items()]
    return "; ".join(parts)


def _shared(groups: list[_Group]) -> dict[str, int]:
    """The item list most groups mostly repeat (written once as ITEMS), with its counts; a list
    is shared when at least two groups name more than half of it."""
    best: tuple[int, _Group | None] = (0, None)
    for group in groups:
        mine = set(group.items)
        overlap = sum(1 for g in groups if len(mine & set(g.items)) * 2 > len(mine))
        if overlap >= 2 and overlap * len(mine) > best[0]:  # the most items not repeated
            best = (overlap * len(mine), group)
    source = best[1]
    if source is None:
        return {}
    return {i: e.qty_max for e, i in zip(source.entries, source.items, strict=True) if not e.note}


def _group_line(menu: ActionMenu, group: _Group, counts: dict[str, int]) -> str:
    """`verb:<item> -> targets: items`; the ITEMS form only when it is clearly shorter (what it
    leaves out plus what it adds is at most half the group)."""
    head = f"{group.verb}:<item>{_targets(menu, group.entries[0])}"
    fits = [
        e
        for e, i in zip(group.entries, group.items, strict=True)
        if not e.note and e.qty_max == counts.get(i, 0)
    ]
    named = {e.id.split(":", 1)[1] for e in fits}
    left_out = [i for i in counts if i not in named]
    rest = tuple(e for e in group.entries if e not in fits)
    if not fits or (len(left_out) + len(rest)) * 2 > len(group.entries):
        return f"{head}: {_item_list(group.entries)}"
    text = "any of ITEMS" + (f" except {', '.join(left_out)}" if left_out else "")
    return f"{head}: <item> = {text}" + (f"; also {_item_list(rest)}" if rest else "")


def _items_line(counts: dict[str, int]) -> str:
    return "ITEMS: " + ", ".join(f"{i} (up to {n})" if n > 1 else i for i, n in counts.items())


def _stem(entry: MenuEntry) -> tuple[object, ...] | None:
    """Neighbours with the same stem share one line: the label before its bracket, the same
    targets and no extras (`None`: the entry has no bracket to differ in)."""
    base, bracket, tail = entry.label.partition(" (")
    if not bracket or not tail.endswith(")") or _extras(entry):
        return None
    return (base, entry.target_ids, entry.zone_ids, entry.max_targets)


def _stem_line(menu: ActionMenu, run: list[MenuEntry], seen: dict[str, str]) -> str:
    """`a, b = Base (tail a; tail b) -> targets` (M36.9 iteration 2: the three parley answers)."""
    if len(run) == 1:
        return _single(menu, run[0], seen)
    base = run[0].label.partition(" (")[0]
    tails = "; ".join(e.label.partition(" (")[2][:-1] for e in run)
    return f"{', '.join(e.id for e in run)} = {base} ({tails}){_targets(menu, run[0])}"


def _singles(menu: ActionMenu, entries: list[MenuEntry], seen: dict[str, str]) -> list[str]:
    runs: list[list[MenuEntry]] = []
    for entry in entries:
        stem = _stem(entry)
        if runs and stem is not None and _stem(runs[-1][-1]) == stem:
            runs[-1].append(entry)
        else:
            runs.append([entry])
    return [_stem_line(menu, run, seen) for run in runs]


def _once(menu: ActionMenu) -> ActionMenu:
    """M38.4: a long target note an earlier entry already wrote for the same target is written
    "as for <that entry>" (a locked place's reason on both travel and unlock)."""
    first: dict[tuple[str, str], str] = {}
    entries: list[MenuEntry] = []
    for entry in menu.entries:
        notes = dict(entry.target_notes)
        for target, note in entry.target_notes.items():
            said = first.setdefault((target, note), entry.id)
            if said != entry.id and len(note) > LONG_NOTE:
                notes[target] = f"as for {said}"
        changed = notes != entry.target_notes
        entries.append(entry.model_copy(update={"target_notes": notes}) if changed else entry)
    return menu.model_copy(update={"entries": tuple(entries)})


def menu_lines(menu: ActionMenu | None) -> list[str]:
    if menu is None:
        return []
    menu = _once(menu)
    groups = _groups(menu)
    counts = _shared(groups)
    lines: list[str] = [_items_line(counts)] if counts else []
    home = {e.id: g for g in groups for e in g.entries}
    done: set[int] = set()
    seen: dict[str, str] = {}
    pending: list[MenuEntry] = []
    for entry in menu.entries:
        group = home.get(entry.id)
        if group is None:
            pending.append(entry)
            continue
        lines += _singles(menu, pending, seen)
        pending = []
        if id(group) not in done:
            done.add(id(group))
            lines.append(_group_line(menu, group, counts))
    return lines + _singles(menu, pending, seen)
