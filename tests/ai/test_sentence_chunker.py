"""Sentence chunker (M4.5, SPEC 6.1 step 3, 11): incremental, abbreviation and quote aware."""

from aidm.dm.sentence_chunker import SentenceChunker, split_sentences


def _feed_all(pieces: list[str]) -> tuple[list[list[str]], list[str]]:
    chunker = SentenceChunker()
    steps = [chunker.feed(p) for p in pieces]
    return steps, chunker.flush()


def test_sentences_emitted_only_when_complete() -> None:
    steps, rest = _feed_all(["The goblin ", "snarls.", " You raise", " your shield. It", " lunges"])
    assert steps == [[], [], ["The goblin snarls."], ["You raise your shield."], []]
    assert rest == ["It lunges"]


def test_boundary_waits_for_next_character() -> None:
    chunker = SentenceChunker()
    assert chunker.feed("The door opens.") == []
    assert chunker.feed(" ") == []
    assert chunker.feed("Cold") == ["The door opens."]


def test_abbreviations_do_not_split() -> None:
    text = "Mr. Vell nods to Dr. Ash. They walk to St. Brin, e.g. the old chapel. Done."
    assert split_sentences(text) == [
        "Mr. Vell nods to Dr. Ash.",
        "They walk to St. Brin, e.g. the old chapel.",
        "Done.",
    ]


def test_initials_and_decimals_do_not_split() -> None:
    assert split_sentences("J. R. Holt waits. The fee is 3.5 coins. Fine.") == [
        "J. R. Holt waits.",
        "The fee is 3.5 coins.",
        "Fine.",
    ]


def test_ellipsis_splits_only_before_a_new_sentence() -> None:
    assert split_sentences("He waits... then nods. The door creaks... Silence.") == [
        "He waits... then nods.",
        "The door creaks...",
        "Silence.",
    ]
    assert split_sentences("Wait… Listen.") == ["Wait…", "Listen."]


def test_quotes_stay_with_their_sentence() -> None:
    text = '"Stay back!" The guard lifts his spear. "Who goes there?" he asks. Then quiet.'
    assert split_sentences(text) == [
        '"Stay back!"',
        "The guard lifts his spear.",
        '"Who goes there?" he asks.',
        "Then quiet.",
    ]


def test_question_and_exclamation_runs() -> None:
    assert split_sentences("Really?! You did it! Yes.") == ["Really?!", "You did it!", "Yes."]


def test_blank_line_is_a_boundary_and_flush_returns_remainder() -> None:
    assert split_sentences("A name list\n\nThe hall is quiet") == [
        "A name list",
        "The hall is quiet",
    ]
    assert split_sentences("   ") == []


def test_chunking_is_independent_of_piece_boundaries() -> None:
    text = 'Mr. Vell smiles. "Go!" she says... and you go. It is 2.5 miles. End'
    whole = split_sentences(text)
    for size in (1, 2, 3, 7):
        pieces = [text[i : i + size] for i in range(0, len(text), size)]
        steps, rest = _feed_all(pieces)
        assert [s for step in steps for s in step] + rest == whole
