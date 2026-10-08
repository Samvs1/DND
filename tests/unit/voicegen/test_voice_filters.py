"""EQ stages (M13.3): RBJ peaking at centre, high-shelf air taper, Butterworth high-pass."""

from aidm.server.voicegen.filters import (
    eq_cascade,
    high_shelf_sos,
    highpass_sos,
    peaking_sos,
    response_db,
)
from tests.unit.voicegen.helpers import SR, real_chain


def test_peaking_gain_at_centre_matches_config() -> None:
    chain = real_chain()
    for name in ("warmth", "presence"):
        cfg = chain[name]
        sos = peaking_sos(cfg["freq_hz"], cfg["gain_db"], cfg["q"], SR)
        at_centre = float(response_db(sos, [cfg["freq_hz"]], SR)[0])
        assert abs(at_centre - cfg["gain_db"]) < 0.3, name
        far = response_db(sos, [cfg["freq_hz"] / 16, min(cfg["freq_hz"] * 5, 20000)], SR)
        assert abs(far).max() < 0.5, name


def test_air_taper_is_a_gentle_shelf_not_a_lowpass() -> None:
    cfg = real_chain()["air_taper"]
    sos = high_shelf_sos(cfg["freq_hz"], cfg["gain_db"], SR)
    at_6k, at_12k, at_20k = response_db(sos, [6000.0, 12000.0, 20000.0], SR)
    assert at_6k > -0.5  # less than 0.5 dB lost one octave below
    assert abs(at_12k - cfg["gain_db"] / 2) < 0.1  # half the shelf gain at the corner
    assert abs(at_20k - cfg["gain_db"]) < 0.3  # full gain (-3 dB) well above, never more


def test_highpass_cuts_rumble_keeps_voice() -> None:
    cfg = real_chain()["highpass"]
    sos = highpass_sos(cfg["freq_hz"], cfg["order"], SR)
    at_cut, rumble, voice = response_db(sos, [cfg["freq_hz"], 20.0, 200.0], SR)
    assert abs(at_cut + 3.01) < 0.1
    assert rumble < -15.0
    assert voice > -0.6


def test_cascade_order_and_flat_mids() -> None:
    sos = eq_cascade(real_chain(), SR)
    assert sos.shape == (1 + 3, 6)  # order-2 high-pass is one section, then 3 biquads
    assert abs(float(response_db(sos, [1000.0], SR)[0])) < 0.6
