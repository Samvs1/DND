# Sound sources

Recordings the sound build (`scripts/gen_dice_sfx.py`, `aidm/server/sfxgen/`) shapes into game sounds.
Everything else in `aidm/web/static/audio/sfx/` is synthesised in this project.

## magic_projectile_impact.flac

- What: "magicProjectile_impact.wav" by **rafaelzimrp**, https://freesound.org/s/570855/
- Licence: **CC0 1.0** (Creative Commons Zero, public domain dedication). No attribution required; credited anyway.
- This copy: Freesound's high-quality mp3 preview decoded to 48 kHz mono and stored losslessly at 0.4x
  level (the mp3 decodes past full scale; the headroom keeps every peak). The build normalises it.
- Used by: the check and save **success** sting and the **natural 20** (`aidm/server/sfxgen/payoff.py`),
  both raised +3 semitones and shaped after the owner's BG3 reference (M26.8, owner picks 2026-10-17).
