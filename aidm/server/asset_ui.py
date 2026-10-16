"""Art keys of the UI chrome (M12.1): the defeat scene, the phone controller tab icons and the M24
dark pixel skin (frame, ribbons, slots, small icons and the Journal and More scenes).

Unlike the other keys these do not come from a data registry; they are the few pictures the views
ask for by name (js/screen/overlays.js and js/controller/defeat.js read `scene.defeat`,
js/controller/tabs.js reads `ui_icon.tab-<id>`, js/controller/ideas.js `ui_icon.act-<kind>` for the
Play tab's idea chips, M18.2). The tab icons point at the owner's v1 tab icons (real art, never
regenerated); the rest start as placeholders for the asset generator.
`subject` is the prompt subject sentence (asset_prompts) and the ASSETS_TODO description.

Public API: `UiArt`, `UI_ART`, `ui_subject`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UiArt:
    key: str
    file: str
    subject: str
    transparent: bool
    v1: bool = False
    hand: bool = False  # owner art copied in by hand: never generated


# The Play tab's idea chips (M18.2, js/controller/ideas.js): one icon per kind of action.
_MEDALLION = (
    ", a small game icon on a round dark slate medallion with a thin gold rim "
    "(an action chip of a phone controller)"
)
_ACTS = (
    ("talk", "Two overlapping speech bubbles (talk to someone)"),
    ("examine", "A brass magnifying glass over a small carved rune stone (examine something)"),
    ("take", "An open hand reaching down to pick up a small leather pouch (pick something up)"),
    ("travel", "A worn leather boot on a winding dirt path beside a wooden signpost (travel on)"),
    ("look", "An open watchful eye with a faint golden glow around it (look around)"),
    ("search", "A small lantern casting warm light over scattered leaves and stones (search)"),
    ("rest", "A small campfire of crossed logs beside a rolled bedroll (rest)"),
    ("trade", "A leather coin purse with gold coins spilling out of it (trade)"),
)

# M24 dark pixel skin (docs/next/GOAL_UI_REVAMP.md): owner-approved generated pieces (real, so the
# generator never touches them). CSS reads the ui_skin keys as properties set by js/ui/skin.js.
_SLOT = "An empty square inventory slot with a dark inset and a thin iron border"
_SKIN = (
    ("ui_skin.frame", "img/ui/skin/frame.png", "An empty dark iron panel frame (9-slice)", True),
    ("ui_skin.stone", "img/ui/skin/stone.png", "A barely visible near-black stone tile", False),
    *(
        (f"ui_skin.ribbon-{c}", f"img/ui/skin/ribbon_{c}.png", f"A blank {c} title ribbon", True)
        for c in ("teal", "crimson", "blue", "olive", "purple", "grey")
    ),
    ("ui_skin.slot", "img/ui/skin/slot.png", _SLOT, True),
    ("ui_skin.slot-selected", "img/ui/skin/slot_selected.png", _SLOT + ", pale cyan", True),
    ("ui_skin.slot-far", "img/ui/skin/slot_far.png", _SLOT + ", dark red", True),
    ("ui_icon.ac-shield", "img/icons/ui/ac_shield.png", "An empty iron heater shield", True),
    ("ui_icon.hourglass", "img/icons/ui/hourglass.png", "An iron hourglass", True),
    ("ui_icon.quill", "img/icons/ui/quill.png", "A dark feather quill", True),
    ("scene.journal", "img/scenes/journal.png", "A map desk by candle and moonlight", False),
    ("scene.more", "img/scenes/more.png", "A stone room corner with a lute and books", False),
)

UI_ART = (
    UiArt(
        "scene.defeat",
        "img/scenes/defeat.png",
        "The quiet aftermath of a lost battle at dusk: a torn banner on a broken spear, a dropped "
        "sword and a guttering torch on an empty hillside under a heavy sky, sombre, no bodies, "
        "no gore, wide 16:9 view with calm dark space in the middle for text",
        transparent=False,
    ),
    UiArt(
        "portrait.scribe.seated",
        "img/portraits/scribe_seated.png",
        "The Scribe seated at his desk (owner art, copied in by hand)",
        transparent=False,
        hand=True,
    ),
    UiArt(
        "portrait.scribe.welcome",
        "img/portraits/scribe_welcome.png",
        "The Scribe, the same character as in the reference images: a skeleton with a pale "
        "skull face and softly glowing violet eyes in a deep purple hooded robe. He has risen "
        "from his candlelit writing desk and raises one open bony hand in a calm, courteous "
        "greeting, the feather quill in his other hand, the open ledger and ink pot on the "
        "desk before him, warm candlelight on a dark background, square, waist up",
        transparent=False,
    ),
    UiArt(
        "portrait.scribe.rewrite",
        "img/portraits/scribe_rewrite.png",
        "The Scribe, the same character as in the reference images: a skeleton with a pale "
        "skull face and softly glowing violet eyes in a deep purple hooded robe, seated at his "
        "candlelit desk, writing in a great open ledger with his feather quill; faint violet "
        "light rises from the freshly written words and a few glowing letters drift up from "
        "the page, warm candlelight on a dark background, square, waist up",
        transparent=False,
    ),
    UiArt(
        "scene.scribe",
        "img/scenes/scribe.png",
        "The Scribe small at his candlelit desk at the bottom of a wide dark room (owner art, "
        "copied in by hand; the dark space above holds the victory text)",
        transparent=False,
        hand=True,
    ),
    UiArt(
        "ui_icon.tab-play",
        "img/icons/tabs/feed.png",
        "An open book with a quill (the play tab)",
        transparent=True,
        v1=True,
    ),
    UiArt(
        "ui_icon.tab-hero",
        "img/icons/tabs/player.png",
        "A knight's closed helmet (the hero tab)",
        transparent=True,
        v1=True,
    ),
    UiArt(
        "ui_icon.tab-scribe",
        "img/icons/tabs/scribe.png",
        "A quill and an inkwell (the Scribe tab)",
        transparent=True,
        v1=True,
    ),
    UiArt(
        "ui_icon.tab-journal",
        "img/icons/tabs/map.png",
        "An open journal (the journal and map tab)",
        transparent=True,
        v1=True,
    ),
    UiArt(
        "ui_icon.tab-more",
        "img/icons/tabs/more.png",
        "A brass cog wheel with three small dots beneath it on a dark slate rounded-square tile "
        "(the more and settings tab of a phone tab bar)",
        transparent=True,
    ),
    *(
        UiArt(
            f"ui_icon.act-{kind}",
            f"img/icons/actions/{kind}.png",
            what + _MEDALLION,
            transparent=True,
        )
        for kind, what in _ACTS
    ),
    *(UiArt(key, file, subject, transparent=clear) for key, file, subject, clear in _SKIN),
)


def ui_subject(key: str) -> str | None:
    """The subject sentence of a UI art key, or None for any other key."""
    return next((art.subject for art in UI_ART if art.key == key), None)
