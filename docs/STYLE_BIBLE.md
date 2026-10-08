# Style bible (Addendum A.4; mandatory prefix of every image prompt, Addendum B.3)

Written after viewing the v1 hero portraits (fighter, rogue, wizard), a class face icon and a spell-school icon.
Image prompts are `PREFIX + subject details from data + the kind note`, built by `aidm/server/asset_prompts.py`
from the two marked blocks below (do not rename their headings). Never name any game, studio, film or real person.

## What the v1 art looks like
- Medium: 16-bit pixel art, hand-placed pixels, crisp stair-stepped edges, a little dithering in shadows, no blur, no smooth gradients.
- Palette: dusky slate blues and teals, weathered stone grey, warm torch amber and ember orange, mossy olive green, parchment cream
  highlights, deep brown-black shadows. Saturated colour is kept for magic: violet, emerald, ember red, icy cyan.
- Lighting: a low warm key from torches, a campfire or a lantern, cool ambient fill, soft pools of light, dark corners, gentle vignette.
- Framing: a small full-length figure stands centred in the lower half of a detailed, lived-in scene (market camp, vaulted cellar,
  wizard's study) that is full of props. Icons are a single object, centred, three-quarter view, filling the cell with a small margin.
- Line quality: selective 1 px dark outline on the subject, none on the background; clean silhouettes, no stray pixels.
- Mood: grounded low fantasy, quietly dangerous, warm and a little worn, adventurous rather than grim.
- Avoid: text, letters, numbers, logos, watermarks, signatures, UI frames or borders, photorealism, 3D render look, anime or chibi
  proportions, glossy plastic shine, modern objects, extra limbs, blurry or smeared pixels, real people, any existing franchise,
  game or film character, costume or emblem.

## Prompt prefix
```text
Retro 16-bit pixel art in a grounded low-fantasy style, hand-placed pixels with crisp stair-stepped edges, limited palette of dusky slate blue, teal, weathered stone grey, warm torch amber and mossy green with deep brown-black shadows, warm low torchlight against cool ambient fill, selective dark outline, quietly dangerous lived-in mood. No text, no letters, no watermark, no logo, no border, no photorealism, no 3D render, no anime.
```

## Kind prompts
- `portrait`: Full-length hero standing centred in the lower half of a detailed atmospheric scene that fits the subject, square composition, the face readable at small sizes.
- `monster_token`: One creature, full body, three-quarter view, centred, plain transparent background, strong silhouette, readable at 64 px, one cell of a 4x4 sheet.
- `item_icon`: One object, centred, three-quarter view, thick dark outline, plain transparent background, one cell of a 4x4 icon sheet.
- `spell_icon`: One emblem-like magical effect or object, centred, glowing in the school colour, plain transparent background, one cell of a 4x4 icon sheet.
- `condition_icon`: One simple symbolic mark of the status, centred, bold shapes readable at 32 px, plain transparent background, one cell of a 4x4 icon sheet.
- `zone_card`: Wide 16:9 battlefield scene seen at a slight angle, open ground in the middle for tokens to stand on, no characters, no creatures, details at the edges only.
- `region_banner`: Very wide panoramic strip 4:1, a landscape or interior vista with a calm horizon band in the middle, no characters, no creatures, a dark soft edge on the left and right.
- `scene`: Wide 16:9 painterly establishing scene behind full-screen interface text, low contrast and dark in the middle third, no characters in the foreground.
- `ui_icon`: One small interface symbol on a dark slate rounded-square tile with a thin worn edge, bold shapes readable at 24 px, matching the reference tab icons, one cell of a 4x4 icon sheet.

## Per-kind notes
- Portrait (`portrait.*`, 512x512): v1 portraits are scenes with a small standing hero. Keep that framing for race, class and
  NPC archetype portraits: same eye level, same pixel scale, props that tell who they are. Two or three real v1 portraits go in as
  style references for every call (Addendum B.3).
- Monster token (`monster_token.*`, 256x256, transparent): a full-body silhouette on transparency, facing left of centre.
  Sheets are 4x4; use one v1 sheet as the style reference. Scale by creature size, not by canvas fill.
- Item, spell and condition icons (128x128, transparent): drawn as cells of a 4x4 sheet, so every cell uses the same outline weight,
  light direction (top left) and margin. Items by category and material, spells by school colour (fire ember, frost cyan, necrotic
  sickly green, radiant gold, force violet), conditions as a plain symbol, never a face or text.
- Zone card (`zone_card.*`, 640x360): terrain only. Muted so tokens and the aim highlights stay readable on top of it.
- Region banner (`region_banner.*`, 1024x256): it sits behind the scene title at low opacity, so keep the middle band calm and
  the contrast gentle. `tier1` is a hopeful dawn, `tier2` a dusk, `tier3` a dark stronghold under storm light.
