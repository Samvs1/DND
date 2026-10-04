"""Dice: parsing, rolling and crit doubling with an injected RNG.

Public API:
- `Rng`: Protocol with `randint(a, b) -> int` (inclusive). `random.Random(seed)` satisfies it.
  Rules code NEVER uses the global `random` module; every roll takes an `rng` argument, so a
  seeded `random.Random` reproduces a whole game.
- `DiceError(ValueError)`: raised for malformed or out-of-range expressions.
- `parse_dice(text) -> DiceExpr`: grammar (whitespace and case ignored)::

      expr := term (("+" | "-") term)*
      term := [count] "d" sides [("kh" | "kl") keep] | integer

  Examples: "1d8", "d20", "2d6+3", "1d4 - 1", "2d6+1d4+3", "4d6kh3", "7". Constants are summed into
  `DiceExpr.modifier`; dice terms keep their order. A dice term cannot be subtracted ("1d6-1d4" is
  rejected: 5e never subtracts dice). On keep ties the earlier die is kept. Placeholders such as
  "MOD" must be substituted by the caller. Results are cached (the returned model is frozen).
- `roll(expr, rng, *, crit=False) -> Roll`: roll a `DiceExpr` or text. `crit=True` doubles the dice
  (not the modifier), per SRD "Critical Hits"; the recorded expression is the doubled one.
- `double_dice(expr) -> DiceExpr`: the crit transform on its own (counts doubled, modifier kept).
- `dice_min(expr)`, `dice_max(expr)`: the bounds of `roll(expr, ...).total`.

Dice are consumed from `rng` in expression order, one `randint(1, sides)` per die.
"""

import re
from functools import lru_cache
from typing import Protocol

from pydantic import ValidationError

from aidm.models.dice import DiceExpr, DiceTerm, DieRoll, Roll

MAX_MODIFIER = 1000

_TERM = re.compile(r"\s*([+-]?)\s*(?:(\d*)d(\d+)(?:(kh|kl)(\d+))?|(\d+))\s*")


class Rng(Protocol):
    def randint(self, a: int, b: int, /) -> int: ...


class DiceError(ValueError):
    """A dice expression that cannot be parsed or is out of range."""


def _make_term(
    count_text: str, sides_text: str, keep_kind: str | None, keep: str | None
) -> DiceTerm:
    count = int(count_text) if count_text else 1
    keep_n = int(keep) if keep is not None else None
    try:
        return DiceTerm(
            count=count,
            sides=int(sides_text),
            keep_highest=keep_n if keep_kind == "kh" else None,
            keep_lowest=keep_n if keep_kind == "kl" else None,
        )
    except ValidationError as exc:
        raise DiceError(
            f"invalid dice term {count}d{sides_text}: {exc.errors()[0]['msg']}"
        ) from exc


@lru_cache(maxsize=1024)
def parse_dice(text: str) -> DiceExpr:
    compact = text.strip().lower()
    if not compact:
        raise DiceError("empty dice expression")
    terms: list[DiceTerm] = []
    modifier = 0
    pos = 0
    while pos < len(compact):
        match = _TERM.match(compact, pos)
        if match is None or match.end() == pos:
            raise DiceError(f"cannot parse dice expression {text!r} at position {pos}")
        sign, count, sides, keep_kind, keep, constant = match.groups()
        if pos > 0 and not sign:
            raise DiceError(f"missing '+' or '-' in dice expression {text!r}")
        if constant is not None:
            modifier += -int(constant) if sign == "-" else int(constant)
        elif sign == "-":
            raise DiceError(f"dice cannot be subtracted in {text!r}")
        else:
            terms.append(_make_term(count, sides, keep_kind, keep))
        pos = match.end()
    if abs(modifier) > MAX_MODIFIER:
        raise DiceError(f"modifier out of range in {text!r}")
    return DiceExpr(terms=tuple(terms), modifier=modifier)


def _as_expr(expr: DiceExpr | str) -> DiceExpr:
    return parse_dice(expr) if isinstance(expr, str) else expr


def double_dice(expr: DiceExpr | str) -> DiceExpr:
    parsed = _as_expr(expr)
    doubled = tuple(
        term.model_copy(
            update={
                "count": term.count * 2,
                "keep_highest": term.keep_highest * 2 if term.keep_highest else None,
                "keep_lowest": term.keep_lowest * 2 if term.keep_lowest else None,
            }
        )
        for term in parsed.terms
    )
    return DiceExpr(terms=doubled, modifier=parsed.modifier)


def _kept_flags(values: list[int], term: DiceTerm) -> list[bool]:
    if term.keep_highest is None and term.keep_lowest is None:
        return [True] * len(values)
    descending = term.keep_highest is not None
    keep = term.keep_highest if descending else term.keep_lowest
    order = sorted(range(len(values)), key=lambda i: (-values[i] if descending else values[i], i))
    chosen = set(order[: keep or 0])
    return [i in chosen for i in range(len(values))]


def roll(expr: DiceExpr | str, rng: Rng, *, crit: bool = False) -> Roll:
    parsed = double_dice(expr) if crit else _as_expr(expr)
    dice: list[DieRoll] = []
    total = parsed.modifier
    for term in parsed.terms:
        values = [rng.randint(1, term.sides) for _ in range(term.count)]
        for value, kept in zip(values, _kept_flags(values, term), strict=True):
            dice.append(DieRoll(sides=term.sides, value=value, kept=kept))
            if kept:
                total += value
    return Roll(expression=str(parsed), dice=tuple(dice), modifier=parsed.modifier, total=total)


def _kept_count(term: DiceTerm) -> int:
    return term.keep_highest or term.keep_lowest or term.count


def dice_min(expr: DiceExpr | str) -> int:
    parsed = _as_expr(expr)
    return sum(_kept_count(t) for t in parsed.terms) + parsed.modifier


def dice_max(expr: DiceExpr | str) -> int:
    parsed = _as_expr(expr)
    return sum(_kept_count(t) * t.sides for t in parsed.terms) + parsed.modifier
