# Player Manual

Everything you need to play at the table, in plain words. The tables in the Reference part are written by the game from its own data, so they are always right. This manual is also inside the game: open the **More** tab on your phone and press **Player manual**, or open the page `/manual` on any screen.

## 1. Getting started

### What you need
- One computer runs the game and acts as the server. It is called the host's computer here.
- A TV or laptop shows the shared screen. Each player uses their own phone (or laptop) as a controller.
- Everyone must be on the same Wi-Fi network. The game is made for one to four players.
- A spoken narrator and music are optional. Without them the game still works, and the story appears as text.

### The two surfaces
- **The screen** (the page `/screen`) is the table everyone looks at: scene art, the story (with what each player typed), the party, the hex battle map, the dice (the roll stage, the rolls on the map), who is acting and who is waiting, votes, the narrator's voice and the music.
- **The phone** (the page `/play`, or just the game address) is your controller. It shows your hero and your buttons, not the story: the story is told on the screen. From top to bottom every tab shows a ribbon and a picture (on Play the place you are in, in a fight the spot your hero stands on with the round, whose turn it is and the turn clock; on Hero your portrait; on Journal, Scribe and More their own scenes), then the tab's content, then your hero (name, level and class, abilities you can use, conditions, HP and the AC shield, plus whose turn it is on the other tabs), and at the very bottom the five tabs: **Play**, **Hero**, **Journal**, **Scribe** and **More**. Each tab has its own colour (Play turns red in a fight). The square button on the picture switches **full screen**, which hides the browser's own bars: if your browser's toolbar covers the tabs at the bottom (Brave on Android does), use it. It is also on the More tab.
- There is no single-device mode. To play alone, open the screen in one window and the controller in another.

### Joining
1. The host starts the game with the LAN option. The screen shows a QR code in the lobby, before the adventure starts. Once play begins the QR code goes away and the space is used for the story and the board.
2. Scan the QR code with your phone, or type the address shown on the screen.
3. Enter your name and press **Join**. The first person in becomes the host. The lobby shows who is at the table, with a **Host** tag. If the host leaves the lobby, the next player who is still there (in the order they joined) becomes the host at once, and everyone sees "<name> is now the host."
4. Everyone builds a hero (see Your hero). When every player has a hero, the host presses **Start the adventure**. The host can type a campaign theme first, or leave it blank for a surprise. Writing the campaign takes up to two minutes. If the live AI cannot write one, the table sees "Tonight the table plays a prepared adventure from the Dungeon Master's shelf; the telling is still live." and plays the built-in campaign with live narration.

### Reconnecting
Your seat is kept for you. If your phone sleeps, loses Wi-Fi or you close the page, open the game address again in the same browser: it remembers your seat and reconnects you by itself. A different browser or device, or cleared site data, gives you a new seat without your hero. When the host restarts the game server, every open page shows the join form again with your name filled in and the line "This table was restarted. Join again to take a seat.": press **Join** (a loaded save still reconnects you to your hero by itself). An old page left open can never take a seat on its own. If your connection drops during a fight, your turn waits 30 seconds for you to come back; after that, and on every later turn while you are still away, the game plays a careful turn for you (see Combat).

### The microphone button
You can dictate your actions. The **Dictate** button next to **Act** only appears when the page is served over a secure connection (the host starts the game with the HTTPS option, or you play on the host's own computer) and your browser supports speech input. Your browser will warn once about the certificate: choose Advanced, then continue to the site. Without the button, use the dictation key on your phone keyboard instead.

### Sound
- Only the shared screen plays sound: the narrator, the Scribe, the music and the dice. Phones are silent. Spoken narration plays only when the host has switched **Spoken narration** on in the Host panel and the host's computer has a Fish Audio key and voice.
- On the **More** tab, the **Screen sound** section changes the narrator, music and dice sound volume and mute on the shared screen from your phone. Any seated player can do this, and the last change wins.
- Dice sounds: every throw knocks and lands on a wooden table, and a check's result has its own sound (success, failure, a natural 20, a natural 1). In a fight the dice land with a short clack and a hit or a miss. Throws, landings, hits and misses come in several versions, so the same one never plays twice in a row; a success and a natural 20 always sound the same. Both are built on "magicProjectile_impact" by rafaelzimrp (Freesound, CC0).
- The **Settings** button on your phone has text speed, text size and a reduce-motion switch. The screen's gear button has the sound settings for the screen.
- When the screen opens, it asks for one click (**Click anywhere to start the table's sound**) because browsers block sound until a page is clicked. It asks again if the browser blocks a clip. Click once and everything plays.

### Tooltips
- Tap a small **?** next to a thing to see what it means. The tip opens as a small popup; close it with its **x**, by tapping elsewhere or with Esc. Turn tooltips off with the **Tooltips** switch in **Settings** (on by default, remembered on your device). The **?** marks are on the Hero tab (stats, features, race traits, conditions, training, spells, spell slots and your gear) and in the shop. In the big grids (abilities and saves together, skills) there is one **?** on the heading, armour class and hit points have one on the hero strip, and in the pack the **?** is on the item you have picked. In a fight there is a **?** on every action slot, on the foes' health words, on the advantage tag, on the Move list's zone facts (dark, cover, rough ground, surfaces) and on your conditions; it is a small target of its own, so tapping the slot still picks it.

Where the **?** marks are:
- **Hero tab and shop**: stats, features, race traits, conditions, training, spells, spell slots and your gear; buy and sell prices.
- **In a fight**: every action slot (attack, Throw, Shove prone, Shove away, Jump, Dash, Dodge and the rest; the Spells and Items buttons open lists whose rows have their own), foe health words, the advantage tag, the Move list's zone facts and your conditions.
- **Play tab**: the Now card (the dark or lit line, the torch chip, gear boons and the light note), the quest offer, the finale and the terms on your roll card (the difficulty, advantage or disadvantage, natural 20 and natural 1).
- **Journal tab**: the main quest, its ways, leads, tasks left behind and favours.
- **Scribe tab and More tab**: the Scribe and his price, and Settings (where the Tooltips switch is).

## 2. Your hero

Open the hero wizard from the lobby (**Create my hero**). It has up to ten steps: Race, Class, Background, Abilities, Skills, Equipment, Spells, Portrait, Name and Review. The Spells step appears only for casters and for races that grant a cantrip. You can go back at any step.

### Races
Your race sets your size, speed, darkvision, bonuses to ability scores and a few traits. A race with subraces asks you to pick one.

<!-- generated:races -->
| Race | Size | Speed | Darkvision | Ability bonuses | Subraces | Traits |
| --- | --- | --- | --- | --- | --- | --- |
| Dwarf | Medium | 25 ft | 60 ft | CON +2 | Hill Dwarf | darkvision, dwarven resilience, stonecunning, dwarven combat training, tool proficiency |
| Elf | Medium | 30 ft | 60 ft | DEX +2 | High Elf | darkvision, fey ancestry, trance, keen senses |
| Halfling | Small | 25 ft | none | DEX +2 | Lightfoot Halfling | brave, halfling nimbleness, lucky |
| Human | Medium | 30 ft | none | STR +1, DEX +1, CON +1, INT +1, WIS +1, CHA +1 | none | none |
| Dragonborn | Medium | 30 ft | none | STR +2, CHA +1 | none | draconic ancestry, breath weapon, damage resistance |
| Gnome | Small | 25 ft | 60 ft | INT +2 | Rock Gnome | darkvision, gnome cunning |
| Half-Elf | Medium | 30 ft | 60 ft | CHA +2, any 2 others +1 | none | darkvision, fey ancestry, skill versatility |
| Half-Orc | Medium | 30 ft | 60 ft | STR +2, CON +1 | none | darkvision, savage attacks, relentless endurance, menacing |
| Tiefling | Medium | 30 ft | 60 ft | INT +1, CHA +2 | none | darkvision, hellish resistance, infernal legacy |
<!-- end generated:races -->

### Classes
There are six classes. Your class sets your hit die (how tough you are), the abilities that matter for you, your saving throw proficiencies and the gear you can use.

<!-- generated:classes -->
| Class | Hit die | Main abilities | Saving throws | Armour | Weapons | Spellcasting |
| --- | --- | --- | --- | --- | --- | --- |
| Fighter | d10 | STR/DEX | STR/CON | all armor, shields | simple weapons, martial weapons | none |
| Rogue | d8 | DEX | DEX/INT | light armor | simple weapons, longswords, rapiers, shortswords, hand crossbows | none |
| Wizard | d6 | INT | INT/WIS | none | daggers, darts, slings, quarterstaffs, crossbows light | INT (prepared, from level 1) |
| Cleric | d8 | WIS | WIS/CHA | light armor, medium armor, shields | simple weapons | WIS (prepared, from level 1) |
| Ranger | d10 | DEX/WIS | STR/DEX | light armor, medium armor, shields | simple weapons, martial weapons | WIS (known, from level 2) |
| Warlock | d8 | CHA | WIS/CHA | light armor | simple weapons | CHA (pact, from level 1) |
<!-- end generated:classes -->

### Backgrounds
Your background gives two skills, sometimes a tool, some gear and a purse of starting gold.

<!-- generated:backgrounds -->
| Background | Skills | Tools | Starting gold | In a few words |
| --- | --- | --- | --- | --- |
| Acolyte | insight, religion | none | 15 gp | You tended a shrine for years and still reach for a prayer when the road gets dark. |
| Soldier | athletics, intimidation | dice set | 10 gp | Barracks drills taught you to hold a line, and the habit of watching exits never left. |
| Criminal | deception, stealth | thieves tools | 15 gp | You made a living in back alleys and know which doors stay unlocked for the right coin. |
| Sage | arcana, history | none | 10 gp | Years among dusty shelves left you with more questions than answers, and a hunger to test them. |
| Folk Hero | animal handling, survival | smiths tools | 10 gp | One brave stand made your village sing your name, and now the crowds expect more of you. |
| Noble | history, persuasion | playing card set | 25 gp | You grew up behind high walls and fine manners, and you are still learning what the world costs. |
| Outlander | athletics, survival | drum | 10 gp | The wilds raised you, and a crowded market feels stranger to you than any forest at night. |
| Entertainer | acrobatics, performance | disguise kit, lute | 15 gp | You have worked every kind of crowd, and you know exactly how a good story lands. |
<!-- end generated:backgrounds -->

### Ability scores
You have six abilities: STR, DEX, CON, INT, WIS and CHA. Pick one of three methods:
- **Point buy**: 27 points to spend. Every score starts at 8 and can go up to 15 before your race adds its bonuses. A score of 13 costs 5 points in total, 14 costs 7 and 15 costs 9. You do not have to spend every point.
- **Standard array**: assign 15, 14, 13, 12, 10 and 8 to your six abilities, one each.
- **Roll 4d6**: the game rolls four dice for each score and drops the lowest die. You then assign the six totals to your abilities.

Your race bonuses are added after that. Each ability has a modifier (the score minus 10, halved, rounded down). Your proficiency bonus is +2 at levels 1 to 4 and +3 at level 5.

### Skills
There are 18 skills, each tied to an ability. Your background gives you two. Your class lets you pick more from its own list, and some races add a pick. You cannot pick a skill you already have. A skill check adds your ability modifier, plus your proficiency bonus if you are proficient. A rogue's Expertise doubles the proficiency bonus on two skills.

### Equipment
You get the gear your background lists and your class's starting kit, and your class lets you choose between a few packages. The wizard shows what each choice contains. You can change your equipment later on the Hero tab (outside fights). An equipment pack (a dungeoneer's, explorer's, burglar's or priest's pack...) comes opened: its torches, rope, oil, candles and the rest are in your inventory one by one, ready to use.

### Spells
Casters pick their cantrips and first spells in the wizard. Only spells the game can run are offered (the full list is in the Reference part).
- **Wizard**: a spellbook of 6 first-level spells, and you prepare spells from it. Prepared spells are your spellcasting modifier plus your wizard level, at least 1.
- **Cleric**: you prepare from the whole cleric list, with the same limit. Your Life domain spells are always prepared and do not count against it.
- **Ranger**: starts casting at level 2 and knows a fixed number of spells.
- **Warlock**: knows a fixed number of spells and uses a few Pact Magic slots that come back on a short rest.
- **Fighter and rogue** do not cast spells. A **High Elf** of any class picks one cantrip from its heritage.

### Portrait and name
Pick a face for your hero, enter a name and pronouns, and write a short backstory if you like (optional). The Review step shows your hit points, armour class, speed and attacks. When you are ready, press **Create hero**.

### Hero files
On the More tab, **Export hero file** saves your hero as a file. In the wizard, **Import a saved hero** loads one, but only in the lobby before the adventure starts, so you can bring a hero to another adventure. If a file cannot be used, the wizard tells you what is wrong.

### A new hero later
A player who joins after the adventure has started builds a hero between scenes (not during a fight). A hero who has died is brought back by **the Scribe** (see The Scribe); there is no way to swap in a different hero during an adventure.

## 3. Playing the story

### Typing your action
On the **Play** tab, type what your hero does in plain words and press **Act**. You can also dictate. The Dungeon Master (an AI storyteller) reads it, decides what is needed and narrates the result on the screen. The Play tab is your controller:
- **The Now card** at the top says what is going on for you: *Your move*, *The story is being told. Watch the screen.*, whose action the Dungeon Master is weighing, your place in line, or that the game is paused. Its label is where you are; under the line, the objective of your active **main quest** (a side quest never shows here), with the **What now?** button beside it (see *What now?* below). The screen's header shows the same main objective as a caption on the picture of the place, under its name on the ribbon.
- **The action box** sits right under it.
- **Ideas**: chips built from the scene: **People here** (talk to someone), **Things here** (take a closer look at something, pick up an item), **Ways on** (travel to a connected place; a locked way is greyed out, and tapping it says why it is shut) and **Anytime** (look around, search, short rest, and **Trade** when a trader is here). Tapping a chip writes the sentence in the action box; it never sends by itself, so you can change it and press **Act**.
- **Your last roll** stays on the tab (label, dice, total and outcome). Your attacks, checks and saves pop up as a card in time with the screen (**Your roll** out of a fight; in a fight a small card with the die, the total against the target number and the verdict, which also appears when a monster attacks you). Damage and healing rolls pop up as a short note.

**Everyone sees what you typed.** When your action starts to play out, the screen shows your words in the story as a small framed card with your hero's portrait, your name and your hero's name (**Ann as Brienne** *"I look inside the cabin"*); the storyteller's telling of what happened follows right under it. The same goes for a creative action or a typed move in a fight. Only *inventory* stays private: its answer goes to your phone alone, so the screen shows nothing for it. The cards stay in the story when the screen is reloaded or a saved adventure is loaded.

The story itself is not repeated on the phone. If you missed a line, open **Journal**, then **Story**: the recent story in full, newest at the bottom (what someone typed reads there as **Ann (Brienne):** "I look inside the cabin").

The Dungeon Master says as much as the moment is worth: a line or two for something small (a look around, small talk, a try that fails), two or three sentences usually, and a little more for big moments (a discovery, a fight starting or ending, a death, arriving somewhere new). It only tells what the game really did: if nothing changed, it describes your attempt, not a result.

The storyteller's prose reads as one paragraph. Plain statements from the game itself each get their own line, on the screen and in **Journal**, **Story** (*Slendee gains True Strike.*, *True Strike ends for Slendee.*, *2 Giant Rats are surprised.*). When someone you talk to answers, their words appear once, on their own line, after their name: **Warden Sellen Ost:** "Leave the lantern." The storyteller leaves the answer to them.

**Picking things up**: type *pick up the pouch* (or *take*, *grab*, *pocket* ...) or tap a **Things here** chip, and an item lying where you are goes into your pack at once; the screen says so in one short line. Things you find in the story that are not ordinary gear (a note, a key, a strange trinket) become **keepsakes**: you carry them, they have no price and cannot be sold, and they are listed under **Keepsakes** in your Hero tab's inventory.

**Quest items and keepsakes**: some things lie in the world because a quest needs them (the orders a smuggler lost, three ember-stones for a beacon). They are **quest items**: picked up, they become keepsakes that belong to a task, and they count for that task's steps. Like every keepsake they cannot be sold or dropped. Some lie in plain sight; others are hidden, and you find them by searching the place where they lie (type *I search the tunnels*, *I rummage through the shelves for a note*, *I look for a loose stone*). Where something is hidden, a typed search is always one roll, Investigation (Perception for *look for*), against the hidden thing's own difficulty, and the story says what the roll says: a success finds it, a failure finds nothing. Lighting a candle or a torch first (*I light a candle, then search the shelves*) lights it and still makes the search. Whatever else the line asks after the search (*..., pick it up and read it*) happens next. A plain keepsake from the story is just that: a memento with no use in any task, even if it looks like something a quest asks for. The storyteller cannot conjure a quest item out of thin air: if it lies elsewhere, you have to go and find it. **One thing is one item**: when two tasks need the same thing in the same place, only one of it lies there and it counts for both; it can be handed to one person only, so the other task just asks you to show it to its person.

**Giving things**: on the **Hero** tab, every keepsake has a **Give** button, and so does every item (tap it in the Inventory first): it opens a list of the people here (alive and not hostile), with a **Cancel**, and hands the thing to the one you pick (not during a fight). A quest item says *Quest item: for <quest>*, a plain keepsake says *Keepsake*. You can also type *give the tide-orders to Gorran* (or *hand*, *offer*, *return*; *give Gorran the orders* works too, and so does *Rook hands the orders over to Gorran*; a quest item can be called by what it looks like, *give Mord the bent silver coin* for *Mord's Coin*, when that person is the one the quest says to bring it to) while that person is here, and your hero really hands it over (setting it down before them counts too: *Rook sets the lockbox in front of Old Renn*, also *before* or *at the feet of*, for something you carry and a person standing here): a keepsake or quest item now belongs to them (that is how a quest step to deliver something is done), and an ordinary item from your pack is a gift they appreciate (see below: only the first few gifts earn favour). Handing over a keepsake earns no favour by itself; finishing the task does. If the person is not here, is hostile, or you do not carry the thing, your phone says so and nothing changes. A count is a count: *Brienne hands the three salt-lanterns to Bram* hands over all three (*all the salt* hands over every one), and if you have fewer the phone says how many there were. A line with several acts does each one in turn: *I pick up the salt and hand it to Gran Tevin* picks it up, then hands it over; words that only set the scene (*Rook steps forward and gives ...*) are told with it, and any other part goes to the storyteller after the rest. **Showing is not giving**: *I show Farran the link and ask about it* keeps the link in your hand; the person only looks. If someone holds a keepsake of yours, you can try to lift it back: *I slip my fingers into his pouch and lift the broken link back out*. That is a Sleight of Hand check (medium in the first region); on a success the keepsake is yours again, on a failure nothing moves and they notice (they like you less). Any other wording that does not hand the thing over changes nothing, and the storyteller does not tell it as given: the thing stays in your pack.

**Paying someone**: type it and the coins really move: *I pay Rutter 4 gold*, *pay Rutter the Gap for a crossing*, *give Rutter 3 gp*, *hand Rutter a gold piece*, *Brienne counts out four silver for Rutter*. Gold is the only coin your hero keeps, so silver and copper are rounded up to whole gold pieces the way the shop rounds a price (four silver costs 1 gold). Paying without naming an amount pays what that person's favour asks, or else 1 gold. The person must be here; the only other refusal is not having that much gold (*Brienne has only 3 gold.*). The rest of the sentence still happens: *I pay Rutter for a crossing and ask him about the drowned girl* pays first, then asks. Paying earns no favour by itself, but when someone's favour asks for payment, paying them is how it is done.

**Handing things and coin to a friend**: type it and it happens: *I hand the herbal poultice to Elowen*, *Brienne gives the spare crowbar to Elowen*, *pass two torches to Rook*, *give Elowen 30 gold* (also *toss*, *slip*, *lend*; *give Elowen the crowbar* works too). The thing, keepsake or coin moves from your hero to theirs at once, and the story says so: *Brienne hands the crowbar to Elowen.* Something you wear or wield comes off first. Handing over is free, also in a fight, as long as your friend stands in your zone. Only the impossible is refused, with the reason: a dead friend, something you do not carry (or not that many), more gold than you have. Saying a drink or use word heals instead (*give Rook my potion to drink*, *pour it into her mouth*), and *give Elowen my thanks* is just words.

<!-- generated:gift_rules -->
- The first 2 different gifts to a person earn their favour; the same thing given again, or more gifts after that, earns nothing more (an item from a quest's reward still counts once).
<!-- end generated:gift_rules -->

### The action queue
Actions are handled one at a time, in the order they were sent. You may have one action waiting at a time. The screen shows who is typing, who is acting now and who is next. Your words appear in the story when your turn in line comes up, not while they wait. Your phone shows **Waiting (n)** while your action is in line. If the storyteller stumbles, you see a plain in-story fallback instead of an error.

### What the Dungeon Master can and cannot do
The storyteller describes the world and decides what happens, but it only does so by asking the game engine. **The engine owns every number**: difficulty, damage, hit points, spell slots, experience and gold. The storyteller cannot make up a damage total, hand out treasure beyond the rules, or invent things that were never introduced. It also tells only what the engine did: a foe still on its feet is never told as dead or still, an attack is told with the weapon really used, nobody is hurt before a roll, a hero at full health bears no wounds, nothing is bought or paid for unless the shop sold it, and a thing your hero does not carry is not there (*I drink my potion of giant strength* with no such potion: her hand finds none). A foe that did not attack this moment is never told lunging, swinging or nearly biting; a spell a foe saved against is told as dodged or shrugged off, not as a hit; a foe that fled is never told killed. It never tells more foes than the fight holds, a hit as a dodge, harm to a foe that is immune to it, or a miss that still burned as a clean miss. A gift your hero really handed over is never told as refused or as going to someone else, a thing a search turned up is told lying where it was found until someone picks it up, a quest offer is never told as accepted before you answer it, taking on a task is never told as finishing it, and an ally who sided with you is never told as joining the party (the party is always your heroes). A foe still in the fight is never told fleeing, a sleeping or senseless foe is never told watching, acting or rising, several blows are told in the order they landed or missed, a gift that won someone over is never told refused, foes from an earlier place never appear in this one, and an offer never holds more figures than its foes. The ending of the tale tells each master's real fate and where the tale really began and ended, and the chosen ending is never closed on a stock line. Nor can it invent quests or quest items: tasks come from the story's people, and steps are checked off by the game (only a step that needs judgement, like calming a ghost, is ticked off by the storyteller); a person you meet who wants help asks a favour through the card (an errand, job or paid task told any other way is not one, and nobody promises coin outside a quest). It does not tell you your next step unless you ask. If you try something clever, the engine rolls for it. Attacking someone who is not already hostile (a friendly or neutral person) asks you first (**Are you sure?**), because they will fight back. Nothing else asks. **Nothing happens until you answer**: the question stays on your phone until you press **Yes, do it** or **No, hold back** (the storyteller's voice does not close it), and the story only says that you hesitate on the brink, and why (*Brienne stands on the brink of violence. Attacking Old Broker Tann is a point of no return: they will fight back. Confirm?*). The attack is told once you confirm, and the fight with them starts at once (also with a master who became your ally). Sending a new action instead counts as **No**.

### Checks and difficulty
When the outcome is uncertain, you roll a d20, add your modifier and compare it with a difficulty number (DC) the engine picks from a fixed ladder:

| Difficulty | DC |
| --- | --- |
| Trivial | 5 |
| Easy | 10 |
| Medium | 15 |
| Hard | 20 |
| Very hard | 25 |
| Nearly impossible | 30 |

The hardest check the storyteller may ask grows with the story, so the first region never asks a Hard check of new heroes:

<!-- generated:check_caps -->
- In the first region a check or a new lock is at most medium.
- In the second region a check or a new lock is at most hard.
- In the third region a check or a new lock is at most very hard.
<!-- end generated:check_caps -->

- A natural 20 on an ability or skill check always succeeds and a natural 1 always fails.
- Saving throws compare the total only. Spell save DC is 8 + proficiency bonus + your casting modifier.
- **Advantage** means you roll two d20 and keep the higher. **Disadvantage** keeps the lower. They cancel each other out.
- **Dark places**: caves and crypts are dark. Out of a fight, every sight and search check there (Perception, Investigation, and any Wisdom or Intelligence check to look around) is rolled at disadvantage, for everyone: darkvision only turns darkness into dim light, which still hinders a careful look. The dice name the reason: *Darkness*. A lit torch, candle or lantern stays lit and travels with its bearer until the next long rest, so one light covers a whole trip through dark places; a torch or candle is used up when lit, a lantern is not. Each hero carries at most one lit light (lighting a second one is refused and uses nothing). You may light yours anywhere, in daylight or where another hero's light already shines: you carry it lit into the next dark place. Walking into a dark place with a light gives the party away: foes there cannot be surprised. Darkness never hides anything outright; it only makes it harder to find.
- **Locks**: a chest, cache or side door can be locked (never the way on, a gateway or a quest item). A way that is shut until you have done something (a region's last place while you have not seen the rest, the next region before its master is dealt with) is no lock: picking or forcing it gets no roll, and the game tells you what opens it. A key the party carries that fits opens it at once, no roll. Otherwise pick it with thieves' tools (a Sleight of Hand check; being proficient with the tools adds your proficiency bonus, proficient with the tools and the skill gives advantage) or force it with Athletics: a crowbar gives advantage (*Crowbar*), and forcing is loud, whether it works or not, so foes in that place cannot be surprised. The story says it once for the place: *The noise carries. Anything nearby is warned.* You can always try again. The lock sets the difficulty, and what it keeps stays out of reach until it is open. Just say what you do ("I pick the lock", "I force the chest open with my crowbar").
- Passive Perception is 10 plus your Perception bonus.
- Out of a fight, a check or saving throw takes over the screen as the **roll stage**: the skill and who rolls, the difficulty on the left and the named bonuses on the right. A moment later the d20 is thrown (two with advantage or disadvantage: the dropped one steps aside, struck through, and the reason is named). The bonuses add into the total and the verdict lands: **SUCCESS**, **FAILURE**, **NATURAL 20** or **NATURAL 1**. The story waits for the verdict, so nothing tells the result early. A natural 20 gets its own show in time with its sound: the die flares gold, the bonuses climb, the banner slams in and a gold spark bursts from the die. Clicking the screen skips to the verdict. The roller's phone shows the same roll as a **Your roll** card, and its verdict never appears before the screen's.

### Impossible actions
Some things no one could do with what is at hand: jumping onto a house roof, lifting a castle, breathing under water with no spell or item that allows it. The storyteller rules these **impossible**, and the feed says so in one line: *Brienne cannot do that: a person cannot jump onto a roof.* Then the story tells the attempt failing. Lifting, hurling or uprooting something no body could move (*I lift the whole thicket out of the ground and hurl it over the treetops*, *I lift the bridge*, a house, a tower, a hill) is ruled impossible by the game itself, the same way, also in a fight. Something that is only hard (*I climb the sheer wall*, *I push the cart off the bridge*) is still a check.
- **There is no roll.** No dice card appears, so a natural 20 cannot make an impossible action work.
- **In a fight the action is not spent.** The attempt does nothing, so you can pick something else on the same turn.
- **Hard but possible stays a check.** Anything a determined person could manage is a roll at a high difficulty (see Checks and difficulty), never an impossibility.
- **Magic, gear and features count.** If you have a spell, item or feature that allows it (Misty Step to reach the roof), the action is possible. Typing a spell outside a fight spends its slot like any cast (see Spells and slots), so it is never free.

### Using your gear
Say what you do with an item in plain words, and the game uses it for real: "I light my torch", "I use my thieves' tools on the chest", "I use the rope to climb down", "I brew a poultice with my herbalism kit", "put out my torch". Wearing and wielding works the same way: "I put on the studded leather armor", "Elowen wields the new warhammer instead", "don my chain mail", "strap on my shield", "swap my mace for the warhammer", "take off my armor", "sheathe my sword", "sling my shield on my back", "holster my light crossbow" really change what you wear (outside a fight). Two gear acts in one line both happen: "I sheathe my longsword and sling my shield on my back". If one half is already so (the sword is already sheathed), your phone says so in a short note and the other half still happens.
- **Only real gear counts.** You must carry the item (bought, looted or from your starting pack). A keepsake named like gear (a "Rope" you were handed in the story) has no use. The Dungeon Master cannot hand you usable gear out of thin air: asking to find a rope or a torch turns up nothing.
- **Gear advantage comes from using the right item.** A rope helps you climb, a crowbar helps you force a lock, a magnifying glass helps you inspect. The dice name the item when it helps (*Rope*, *Crowbar*). Naming an item that does not fit (forcing a lock with a rope, searching with a lute) gives no advantage where the game knows what would help: a lock, a dark place, climbing, searching. Anywhere else the Dungeon Master judges your idea as usual ("I tie up the goblin with my rope").
- **One item use per action.** Gear is never refused just because it would not help: the use happens, the item is spent as usual and the game tells you it had no special effect. Only the impossible is refused (an item you do not carry, a target out of reach, an action you already spent, relighting a light that is already lit) and then nothing is used up.
- **Lights**: a lit torch, candle or lantern stays lit and travels with you until the next long rest. You can light it anywhere, daylight too: it lights the next dark place you walk into. Putting it out is free, in or out of a fight ("put out my torch", "douse the lantern", "pinch out the candle", "blow out my candle", "shutter the lantern"). A torch or candle is then used up; a lantern can be lit again later. One sentence can do two things: "I light a candle, then look around" lights the candle and then searches, and "I pinch out the candle and we crouch low" puts it out first. Lighting a light you already carry lit says so in a plain line (*Rook already carries a lit torch: it is already lit.*), and nothing is used.
- **Light and stealth**: a light in a dark place gives the party away. When you light one there you hear: *Your light shows you the way, and shows you to anything waiting here.* Foes in that place cannot be surprised, and a fight there starts with *They saw your light coming. No surprise.* Putting the light out does not undo it. To sneak, put your light out BEFORE you walk into the next dark place.
- **Sealed packs**: a hero made before starting packs were opened at creation may still carry a sealed pack (a Dungeoneer's Pack as one item). Open it from its item card (**Open the pack**) or by typing "open my pack"; it becomes its contents (torches, rope, crowbar and the rest). It takes time, so not during a fight.
- **At a long rest**: crafting gear (the herbalism kit: a poultice for 2 camp supplies, proficiency needed) is used while the party rests. Say "I brew a poultice" and the party votes on a long rest; the poultice is made after the rest, from the supplies left.
- **What the screens show**: darkness and light are never hidden.
  - *Dark places.* The scene picture and the top of your phone dim and carry a **Dark** badge, and your Now card says *It is dark here.* On the hex map a dark zone is dimmed with a **Dark** mark; zones a light reaches glow warm and carry **Lit**, and the hero carrying the light has a small flame on their token. The legend says it: *Dark: heroes without darkvision attack into it at disadvantage.* A fight in the dark starts with *It is dark here. Heroes without darkvision attack into dark zones at disadvantage.*
  - *A lit dark place.* While a hero carries a lit light, the badge reads a warm **LIT** instead of **Dark**, the picture and the top of the phone are not dimmed, and your Now card says *Your torch lights the way.* (torch, lantern or candle).
  - *On your phone in a fight.* Foe chips carry a **Dark** badge when the zone they stand in is dark, the **Move** list says **Dark** or **Lit** for every zone, and while you stand in the dark with an unlit light in your pack the hotbar has a **Light torch** slot (a bonus action).
  - *Advantage and disadvantage on fight rolls.* A fight roll that had either shows both d20s on the strip under the board and in THIS ROUND (the dropped one dimmed) with a tag that names the reason, like **DIS · Darkness** or **ADV · Hidden**; your phone's fight card shows the same tag. A spell with no roll (Sleep, from a scroll or a slot) gets one line there too: *Elowen reads Sleep: Goblin A, Goblin B asleep*.
  - *Who sees in the dark.* A hero with darkvision has an eye icon on the party list and in the turn order.
  - *Who carries a light.* The bearer has a **Torch lit** or **Lantern lit** chip (party list, hero strip and Now card) and a **Put out light** button (Now card, **Items** and the Inventory tab). Putting it out is free. When you light a light in a dark place the phone shows the warning line too. A fight that a light gave away starts with *They saw your light coming. No surprise.*
  - *Idea chips.* **Light a torch** shows in a dark place when you carry a light that is not lit. A locked thing carries a **Locked** badge in the list of things here.
  - *Gear boons.* Gear that gives you advantage (a rope, a magnifying glass) shows as a chip on your Now card while it lasts.
  - *Item card.* Tap an item in the Inventory tab: **Use** says what it does here (*Light this dark place*) and why it is off when it is (*Only works in a dark place.*); a use aimed at a locked thing has a picker of the locked things here. It does the same as typing the words. In a fight use gear from the hotbar.

**Every use of gear, from the game's data:**

<!-- generated:item_uses -->
| Item | Use | Where | Cost in a fight | What it does |
| --- | --- | --- | --- | --- |
| Torch | Light the torch | in a dark place | Bonus action | lights the place; shows you to anything waiting |
| Torch | Throw the lit torch at a creature | in a fight | Action | 1 fire damage |
| Torch | Throw the lit torch into a zone | in a fight | Action | fire into a zone (sets oil alight) |
| Candle | Light the candle | in a dark place | Bonus action | lights the place; shows you to anything waiting |
| Lantern, hooded | Light the lantern | in a dark place | Bonus action | lights the place; shows you to anything waiting |
| Lantern, bullseye | Light the lantern and search closely | in a dark place | Bonus action | lights the place; shows you to anything waiting |
| Crowbar | Force this open with the crowbar | at a locked thing | - | forces the lock |
| Rope, hempen (50 feet) | Climb or cross here | anywhere | - | advantage on athletics |
| Rope, silk (50 feet) | Climb or cross here | anywhere | - | advantage on athletics |
| Grappling hook | Climb or cross here | anywhere | - | advantage on athletics |
| Climber's Kit | Climb or cross here | anywhere | - | advantage on athletics |
| Piton | Climb or cross here | anywhere | - | advantage on athletics |
| Magnifying glass | Inspect closely here | anywhere | - | advantage on investigation |
| Spyglass | Look far from here | anywhere | - | advantage on perception |
| Cartographer's Tools | Chart the way ahead | anywhere | - | charts the way ahead |
| Navigator's Tools | Chart the way ahead | anywhere | - | charts the way ahead |
| Thieves' Tools | Pick this lock | at a locked thing | - | picks the lock |
| Disguise Kit | Put on a disguise | anywhere | - | advantage on deception |
| Forgery Kit | Forge a document | anywhere | - | advantage on deception |
| Bagpipes | Perform here | anywhere | - | advantage on performance |
| Drum | Perform here | anywhere | - | advantage on performance |
| Dulcimer | Perform here | anywhere | - | advantage on performance |
| Flute | Perform here | anywhere | - | advantage on performance |
| Horn | Perform here | anywhere | - | advantage on performance |
| Lute | Perform here | anywhere | - | advantage on performance |
| Lyre | Perform here | anywhere | - | advantage on performance |
| Pan flute | Perform here | anywhere | - | advantage on performance |
| Shawm | Perform here | anywhere | - | advantage on performance |
| Viol | Perform here | anywhere | - | advantage on performance |
| Dice Set | Gamble here | anywhere | - | advantage on performance |
| Playing Card Set | Gamble here | anywhere | - | advantage on performance |
| Healer's Kit | Stabilize a fallen ally | on a fallen ally | Action | stabilizes a dying ally |
| Herbalism Kit | Brew a poultice from camp supplies | at a long rest | - | makes herbal poultice from 2 camp supplies |
| Fishing tackle | Fish here for camp supplies | at a fitting place | - | adds camp supplies |
| Hunting trap | Set a trap for camp supplies | at a fitting place | - | adds camp supplies |
| Antitoxin (vial) | Drink the antitoxin | anywhere | Bonus action | advantage on poison |
| Oil (flask) | Throw the oil at a zone | in a fight | Action | leaves oil in a zone |
| Alchemist's fire (flask) | Throw the fire | in a fight | Action | 1d4 fire damage |
| Acid (vial) | Throw the acid | in a fight | Action | 2d6 acid damage |
| Holy water (flask) | Throw the holy water | in a fight | Action | 2d6 radiant damage |
| Caltrops | Scatter the caltrops in a zone | in a fight | Action | leaves caltrops in a zone |
| Ball bearings (bag of 1,000) | Spill the ball bearings in a zone | in a fight | Action | leaves ball bearings in a zone |
| Spell scroll (any) | Read the scroll | anywhere | Action | casts the scroll's spell |
| Burglar's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Diplomat's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Dungeoneer's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Entertainer's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Explorer's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Priest's Pack | Open the pack | anywhere | - | opens the pack into its contents |
| Scholar's Pack | Open the pack | anywhere | - | opens the pack into its contents |
<!-- end generated:item_uses -->

**Gear in a fight.** On your turn open **Items** on the hotbar: it lists your potions and each fight use of your gear with its cost (**Action** or **Bonus action**). Tap the use, then pick its target (a creature, a fallen ally or a zone). You can also type it: "I throw the acid at the goblin", "I scatter the caltrops in the gate". A throw reaches your zone or a touching one. A use that has no special effect still happens and is spent.
- **You can only use what you carry.** Whatever you try in a fight, typed or as a free action ("I throw my waterskin at it"), the game checks your pack: an item you do not carry, or a keepsake, is only an attempt and nothing happens.
- **Throw anything you carry** (action): an item with no fight use of its own is an improvised weapon: a ranged attack (no proficiency bonus), 1d4 plus your Strength modifier on a hit. The item is gone, hit or miss. Weapons are thrown from the attack menu instead: a thrown weapon (a dagger, a handaxe, a javelin) leaves your hand and pack and lands at this place, so pick it up after the fight.
- **Weak to a substance**: some creatures are hurt by what an item carries. Water splashed on a fire elemental (a thrown waterskin that hits) deals it 1 cold damage on top of the throw. The foe's traits are known to the Dungeon Master, so a clever idea counts.
- **Alchemist's fire** (action): a ranged attack with it as an improvised weapon (no proficiency bonus). A hit deals 1d4 fire and sets the target **burning**: 1d4 fire at the start of each of its turns, for up to 10 rounds or until the fight ends. Anyone in the same zone can spend their action on **Put out the flames** (a DC 10 Dexterity check; it shows on the hotbar when you are burning). The flask is used up, hit or miss.
- **Acid** (action): the same kind of throw, 2d6 acid on a hit.
- **Holy water** (action): the same kind of throw, 2d6 radiant on a hit, but only to undead and fiends; at any other creature the flask still shatters on a hit and is spent, with no special effect.
- **Oil** (action): splashes a zone with oil (difficult ground). Fire sets it alight: everyone in the zone takes 2d6 fire (DC 12 Dexterity save for half) and the zone burns.
- **Caltrops** (action): scattered in a zone, whoever walks in makes a DC 15 Dexterity save or takes 1 piercing. **Ball bearings** (action): whoever walks in makes a DC 10 Dexterity save or falls prone.
- **Torch** (bonus action to light it). A **lit torch** can be thrown as an action: at a creature it is a ranged attack that deals 1 fire on a hit; into a zone it lands there, and into oil it sets the oil alight. Throwing it ends your light.
- **Healer's kit** (action): stabilizes a dying ally in your zone, no roll; it has 10 uses.
- **Healing potions**: drinking one is a bonus action (from **Items**, or from the sheet outside a fight). A potion drunk at full health is still drunk: it is gone and the game says it had no special effect. Outside a fight you can also type it: *I drink my potion*, *use the restorative draught*, *I pour my potion into Rook*, *Brienne binds Rook's wounds with her herbal poultice*. A drink word (*drink*, *quaff*, *swallow*) always means you drink it yourself, whoever else the line names (*I drink the poultice Brienne gave me*); to give it to a friend, name them first (*I help Rook drink my potion*). A hero's own draught can be given to them too (*pour his potion between Rook's lips*). The engine heals for real, or says plainly why not (a dead hero cannot be helped, and nothing is used).

**Spell scrolls.** Anyone can read a scroll, spellcaster or not: "I read the scroll of sleep at the goblins", or tap it under **Items** in a fight. Reading takes your action in a fight, and works outside a fight too. The spell is cast at the scroll's own level with the scroll's own numbers, not yours: a 1st or 2nd level scroll has save DC 13 and +5 to hit, 3rd or 4th DC 15 and +7, 5th or 6th DC 17 and +9, 7th or 8th DC 18 and +10, 9th DC 19 and +11. No spell slot is used, and the scroll is gone once read. It is aimed like the spell: at a creature, at a zone (Sleep lands in the zone of the foe you aim it at) or at nobody (a spell that centres on you). Outside a fight a harmful spell read at someone starts a fight: at a person you were talking to you are asked **Are you sure?** first, and on yes the scroll is read as the fight's opening strike. Read at nobody outside a fight, it is spent with no special effect.
- **Copying a scroll** (wizards): instead of reading it, a wizard can copy a scroll into the spellbook from the **Spellbook** tab of the sheet, outside a fight. It must be a wizard spell of a level you can prepare and not already in your book. It costs 50 gold per spell level (an Evocation wizard pays half for an evocation spell), and the gold and the scroll are spent. The spell is then yours for good.

### Trouble ahead
When the party arrives somewhere dangerous, the game warns you first and nothing starts without a choice. Every phone with a hero shows a **Trouble ahead** box: who you face and how hard the fight looks (trivial to deadly). A creature with a breath weapon or a like blast is rated by what one blast does to your heroes' hit points, not only by its experience value: a young dragon whose breath can drop a hero is shown as deadly. Each foe's usual damage in one turn (its attacks, or its best damaging spell) also counts against your heroes' hit points and armour: a bear that can tear half the hit points off one of your heroes in a turn is shown as at least hard. A foe that shoots from behind heavy cover (three-quarters) makes the fight one step harder. A region's master is rated by its real strength: fewer or more hit points than its kind (see below) count, and so would any extra attacks it gets. The word only warns you; it never changes which creatures you meet. The first player to press a choice decides for the whole party:
- **Fight**: the fight begins. Attacking them by typing (*I charge the mephit*) is the same answer: any fight that starts here answers the warning, and foes you have already beaten never come back from it.
- **Ambush them**: the whole party rolls Stealth. If at least half succeed, the foes are surprised. The fight starts either way.
- **Slip away**: each hero rolls the better of Stealth and Athletics. If at least half succeed, the party goes back to where it came from and there is no fight. If not, the fight begins.
- **Parley**: your hero (the one whose player pressed it) rolls Persuasion. On a success there is no fight. On a failure the fight begins. Typing works too, while the choice waits: talking to them (*I call out and ask whether he will let us pass*, *I persuade them to stand aside*) is the parley with Persuasion, *I threaten him* uses Intimidation and *I lie to them* or *I bluff* uses Deception. Peaceful words to the foes count too, with or without their name (*Easy now, friend in the robe, we don't want a fight*), and so does a question put to a foe or the master by name (*I ask Grinner Voss what the Silent Company collects*). Before such a line answers the choice, your phone asks first, with the same **Are you sure?** card: *This answers the fight offer as a parley: one roll, a failure starts the fight. Confirm?* **Yes, do it** makes the one roll; **No, hold back** keeps the choice waiting. That one roll answers the choice; there is no second roll. Naming one of your friends (*I ask Elowen what she thinks*) is just talk, and so is speaking to someone else standing there who is not one of the foes (*I ask Dreda who she is*): the choice keeps waiting. Talking a region's master down is an easy check in the first region (DC 10) and a medium one after that (DC 15), the same as talking your way past other trouble; a success also warms the master to you (see Quests and the journal for how a master can become an ally). A parley that holds with a master **before** you have finished the way of peace buys peace for now only: the line says so (*Brother Mallow lets you be for now, but the way on is not yet open: finish the peaceful way (The Lullaby's Leash), or face Brother Mallow*), and the master meets you again with the same choice the next time you arrive there. If you have finished the **way of peace** with a master, the master hears you out: the button reads **Parley (sure to hold)** and it holds without a roll. Reaching the master never decides for you: you still choose, and you can still fight. Handing the master the thing the way of peace asks for (or winning the master over any other way) does not answer for you either: the choice keeps waiting, now as **Parley (sure to hold)**, until you pick. You can hand it over by typing while the choice waits (*Rook steps forward and gives Caul's Bait-Cache to Abbess Marwen Salt*): a master takes the thing their way of peace asks for even while not yet friendly, and a master who yielded to you takes what you give. The **Are you sure?** card belongs to the hero who said the line: only that hero's player answers it (another player who presses **Yes** is told whose card it is, and nothing happens).
- **Attacking while the choice waits**: typing an attack on one of the foes (*Rook attacks the bandit with his shortbow*, *I put an arrow in the zombie*) or a harmful spell at them (*I cast Burning Hands at the violet fungus*, *I fling a scorching ray at the gnoll*) answers the choice as **Fight**. Everyone rolls initiative as usual, and your line waits for your hero's turn: then it is played exactly as typed (the attack is rolled, the spell is cast, or the game says why not, for example out of reach). Your phone says so: *The fight starts. What you typed waits for Rook's turn and is played then, as typed.* Sneaking up first (*we creep up and ambush the ghoul*) is not an attack: that is still up to the storyteller (or press **Surprise**).
- **Demanding surrender while the choice waits** (*Drop your weapons and yield!*): foes who can never yield (the undead, constructs, oozes and plants) get one plain line and no roll (*The zombie will not yield: the dead do not surrender.*), and the choice keeps waiting. Other foes hear it as a parley with Intimidation (with Persuasion when you offer them mercy), asked first like any typed parley.

The first place of each region is always safe. Fights start only from a warning you answer or from what the party does, never from a timer. Fights are built for your party's size and level: a place's creatures are an easy fight for the heroes you have, and when the creatures that haunt a place are too strong for your party, weaker creatures of the same kind of place stand in (an easy place never fields a creature whose blast alone makes it a harder fight). The master of a region waits in its last place with company: foes from around the region who make it a fair fight, at most one companion for each hero. A master too strong on its own for one or two heroes comes in weakened, with fewer hit points (never below half). Facing three or more heroes a master comes in with all the hit points of its kind in every region (the hero count only weakens a master for one or two heroes). It also carries **Master's Resolve**: advantage on saves against being stunned, paralysed, charmed, frightened, incapacitated or held fast, so one spell rarely takes it out of the fight. Whatever your party's size, a master is never weaker than the region's own fights: one weaker than the strongest group the region's places can field comes in with more hit points (at most double). A master whose blast alone is more than a fair fight comes without company, and a story never picks a master whose breath or area spell (a fireball and its kin) would drop a hero of that region in one blast.

### Votes
Some things need the whole table: **travelling**, **resting** (short or long) and **browsing a shop**. To ask, type it on the Play tab (*take a short rest*, *make camp* for a long rest, *go to* a place; a longer sentence works too, *we make camp among the thorns and take a short rest* or *the party sets watches and rests for the night*) or press **Trade** when a trader is here; a vote then opens on every phone (as a card at the top of the page) and on the screen. Typing *look around* or *inventory* gets an instant answer without a vote. A place further than the next road works too (*I travel to The Skiff-Road*, *we make our way back to Hollowgate Cross, then on to the Barrow*): the vote names the way (*travel to The Skiff-Road (by The Brine-Veil)*) and the party walks it road by road. The walk stops where something needs you (a fight, foes waiting for your answer, a crossing into the next region that asks first, a road that is shut) and says where it stopped and why: *The party stops at The Brine-Veil: something waits here for your answer. The Skiff-Road lies further on: travel on when ready.* A place no open road reaches is refused with that reason.
- Each player presses **Ready** or **Not yet**. The person who asked counts as ready.
- It passes as soon as more than half are ready and fails as soon as half or more decline.
- If time runs out (30 seconds), it passes when more are ready than declined. Silence does not block the table.
- Only connected players with a living hero vote. The host can press **Host: decide now** to force the open vote.

### The map and travel
The **Journal** tab has a **Map** section. It shows the region as places you can visit, with your current place marked and unexplored places in fog. Some places are locked until something happens in the story. Under **Travel**, each place connected to yours has a **Travel to** button: press it and the table votes. A locked way says why it is shut, under its button, when you tap its chip, and when you try to go there: a region's last place (where its master waits) *stays shut while <region> still hides places you have not seen: 2 left*, naming the places when you know the way to them, and the way into the next region *opens once the master of <region> is dealt with*. That is a fact of the world, not a hint. When a master is dealt with while the region still hides places you have not seen, the story says so the same way (*The Sluice Gate stays shut while The Slatewash Braes still hides places you have not seen: 1 left (Mossbarrow Copse)*) instead of saying the way on is open. You cannot travel during a fight. Arriving may start a story scene, a warning (see Trouble ahead) or someone asking for help (see Quests and the journal). Crossing into the next region with unfinished side quests asks first (see Leaving a region).

### Rests
Rests also need a vote and happen between fights.
- **Short rest**: every living hero regains half of their maximum hit points (a hero at 0 HP wakes up), and abilities that come back on a short rest are restored. You can take at most two short rests between long rests.
- **Long rest**: every living hero returns to full hit points and regains all spell slots and abilities. Temporary hit points and short effects end, and death save counts reset. A long rest costs **10 camp supplies for each living hero**. If the party does not have enough, it is refused, and the game says how many supplies are missing (a third short rest is refused the same way, naming the limit).
- **Camp supplies** are shared by the whole party. The party starts with 40. Buy rations, baskets, stew kits and hampers in shops, or find them as loot. Fallen heroes are not revived by resting and do not pay.

### Shops
When the table agrees to browse a shop, your phone opens the shop. Every player trades for themselves with their own gold.
- **For sale** lists what the trader sells. **Your pack** lists what you can sell.
- A trader sells different things depending on their trade.
- Every region has at least one trader who sells weapons, armour and healing. When a story has no such trader in a region, a peddler (a general store) waits at its first, safe place.
- A general store always has camp food, a Herbal Poultice (10 gp), a Traveller's Tonic (25 gp), a Potion of Healing (50 gp) and a Healer's Kit, and at least one weapon and one piece of armour. A smith always has a Herbal Poultice and at least one potion.
- You cannot sell what you are wearing or wielding: take it off first.
- Gold comes only in whole coins. An item worth less than 1 gp costs 1 gp on its own, but a lot costs its true price rounded up: a camp ration is worth half a gold piece, so one costs 1 gp and ten cost 5 gp. The shop shows the price of the quantity you picked and, for such cheap goods, a note like **2 for 1 gp**. Goods worth a part of a gold piece above 1 gp show the same note: a Hearty Meal Basket is worth 1.5 gp, so one costs 2 gp and the note reads **2 for 3 gp**.
- A trader pays half an item's value in whole gold, so an item worth less than 2 gp (a hammer, a rope, incense) fetches nothing and the trader says so.

<!-- generated:shop_rules -->
- You buy at 100% of an item's value, rounded up, never less than 1 gp.
- A shop buys from you at 50% of the value, rounded down.
- You can trade up to 10 of an item at a time.
- A trader whose trade is unclear counts as a general shop.
- Every region has a trader who sells weapon, armor, potion.

Kinds of shop:

- **General** sells gear, tool, supply, key, potion (about 14 items), always with at least one weapon, armor.
- **Smith** sells weapon, armor (about 14 items), always with at least one potion.
- **Alchemist** sells potion, supply (about 8 items).
- **Scribe** sells scroll (about 10 items).
- **Provisioner** sells supply, gear (about 8 items).
<!-- end generated:shop_rules -->

Things you can buy that matter most:

<!-- generated:consumables -->
| Item | Kind | Effect | Price |
| --- | --- | --- | --- |
| Potion of Healing | potion | heals 2d4+2 | 50 gp |
| Potion of Greater Healing | potion | heals 4d4+4 | 150 gp |
| Potion of Superior Healing | potion | heals 8d4+8 | 500 gp |
| Potion of Supreme Healing | potion | heals 10d4+20 | 1500 gp |
| Herbal Poultice | potion | heals 1d4+1 | 10 gp |
| Traveller's Tonic | potion | heals 2d4 | 25 gp |
| Restorative Draught | potion | heals 3d4+3 | 100 gp |
| Healer's Elixir | potion | heals 6d4+6 | 300 gp |
| Camp Ration | supply | adds 1 camp supply | 0.5 gp |
| Hearty Meal Basket | supply | adds 3 camp supplies | 1.5 gp |
| Stew Kit | supply | adds 5 camp supplies | 2.5 gp |
| Feast Hamper | supply | adds 10 camp supplies | 6 gp |
<!-- end generated:consumables -->

### Loot and gold
After a victory the party's loot is gathered into one reward: experience for every living hero, gold shared out evenly (any remainder goes to the first heroes), items handed out in turn, and any camp supplies found go to the shared pool. Gold is kept per hero and shows on your sheet. The adventure's side quests pay gold, experience and sometimes an item when they are completed (never the very thing the quest had you fetch: that goes where the quest said); a region's main quest is rewarded by the experience for dealing with its master; favours earn goodwill only, never gold or experience. Reaching new places and clearing them (a fight won or a parley there) pays experience too, and so does dealing with a region's master, by a fight or by an alliance. These amounts are fixed per region, so a party that talks its way through meets each master at the same level as one that fights: about level 2 at the first master, 3 at the second and 4 or 5 at the last.

<!-- generated:milestone_xp -->
| Region | Reaching a new place | Clearing it | Dealing with the master |
| --- | --- | --- | --- |
| First | 50 | 100 | 150 |
| Second | 100 | 200 | 600 |
| Third | 400 | 800 | 1,000 |

The last master dealt with adds 1,600 more. Each pays every living hero once.
<!-- end generated:milestone_xp -->

### Quests and the journal
The **Journal** tab has three sections: **Journal**, **Map** and **Story** (the recent story in full, for catching up). The Journal section is laid out like this. At the top the **main quest** of the region is pinned: its title, its objective and every **way** you have found so far (Force, Peace, Cunning), each with the steps you have done ticked off; a way that is finished is marked *Done*. Under it the quests are grouped: **Active**, **Offered** (who asked, and the objective they told you), **Leads** (plain lines about rumours and hints of tasks still to be found), **Completed**, and **Left behind and failed** (greyed out and folded away; tap to open). Each quest card shows who gave it, the objective, its done steps ticked off and a short log of what happened in it (older log lines fold away). The journal shows what you have **done**, not what to do next: the next step is told only by the *What now?* help. It also keeps what is known so far and earlier scenes. On the phone, a short **toast** at the top tells the quest moments (a task taken on, a step done, a quest completed, a way found, a lead, a task left behind, a keepsake handed over), and the screen's story shows the same moments as lines. Each region has one **main quest**, active from the moment you arrive: it ends when the region's master is defeated, or when you finish another way of dealing with them that you discover by talking to the right people or by doing one of its steps. Quests are made of steps, and the game checks a step off by itself as soon as what it asks has really happened (you went there, won the fight there, carry the item, handed it over, met the person). **The game writes every step line** from exactly what it checks: *Go to Weeping Bastion*, *Win the fight at Saltcellar Tunnels*, *Find the Choir tide-orders at Saltcellar Tunnels*, *Give the lockbox to Renn*, *Meet Sister Ilka Wellmoss*, *Make Ulva friendly*, *Learn about blackpine*, *Pay Rutter the Gap 4 gold*. The story of the task (why it matters, what the giver hopes for) is in its objective, never in a step, so a step never promises a deed the game does not check. A fight step names the place only: who waits there you see when you get there. A side quest never asks you to meet a region's master (that meeting is the main quest's); it asks you to come back to the person who gave it. A task whose giver asks you to come back or bring something back (*recover the ledger*, *come back with word*) ends with **Meet <the giver>**: it is done when you go back to them after the rest, not when you pick the thing up. Every step is one the game can check: a step only the story could judge is never part of a task. Only quest items the game placed count (for every task that needs that thing); see *Quest items and keepsakes* above. A step that asks you to **learn** something is done where you learn it, while its task is active: **ask the person who knows it** (the one who gave you that task, someone whose own story it is, or someone whose secret is about it) and name what you ask about (*I ask Bramble to tell me what he carries*, *Sister Thena, who was Brother Mallow?*); the game records it at once and the person answers in the story. Things the storyteller only mentions in passing do not count. A place whose name holds it teaches it when you **look around** or **search** there (arriving is not enough); a step only a place can teach simply reads *Go to <place>*. A find or a told secret there, or finishing the task it names, teaches it too; a visit long ago does not count. People open up as they warm to you: once someone likes you enough to tell a secret (friendly, for most), asking them a question tells it. A **clue** teaches it too: a note, letter or carving that tells what the step asks. Some lie in the world for the task (*Learn about blackpine from the Notes on Blackpine*), and the storyteller can make something you find into one when it tells exactly that. Picking a clue up or reading it (*I read the spore-ink note*, *examine the note carefully*) counts, even if you later hand it over. **A visit counts only after you took the quest on**: places you went before do not tick a *Go to* step, and neither does the place you stand at when you accept (the next arrival there counts; the game never sends you to the giver's own place). When a step is done by what you did before (you already carry the thing, already won that fight, stand with that person), the story says what did it. Other work you did before taking a quest on counts once it is active. An offered quest does not move until it is accepted; when every step of an accepted quest is done, it completes and pays its reward once.

**Quests come from people.** Nobody hands you a list. When the party arrives where someone needs help, that person asks (one ask per arrival): the story tells it, and every phone with a hero shows a card at the top of the Play tab, *<name> asks: <quest>*, with what they want and two buttons. The first player to answer decides for the party:
- **Accept**: the quest becomes active. Anything you already did for it counts at once.
- **Not now**: nothing is lost and nobody minds. The quest stays offered, and the card comes back the next time you arrive where that person is.

You can also answer in words while the person who asks stands with you: a plain yes (*Sure, we'll take the job, Merre*, *Yes, we will go up to the sluice gate*, *count us in*) is **Accept**, and a plain no (*No, we have other business*, *not now*, *we'll pass*) is **Not now**, exactly as the buttons.

The full card shows on the **Play** tab. On the other tabs a slim line (*<person> asks: <quest>*) with an **Answer** button stays at the top and takes you back to Play, so it never covers your sheet or journal.

**Favours.** Besides the quests of the story, someone you meet may ask a small favour of you (look in on a place, carry a keepsake to someone, find out something, pay them for a service). It comes through the same card, with the same **Accept** and **Not now**. A favour has one step and then **Meet <the person who asked>** (come back and tell them; not when the step itself already ends with them, such as giving them something or paying them); the game checks both off like any other steps, and only one favour can be open at a time (each person asks at most one). A favour's place is always one its own words name: if there is none to go to (they ask about the place you stand in), the favour is simply to come back to them later. Doing it earns that person's goodwill, never gold, experience or items, and the person never promises you a reward for it (nor does the story tell coin paid for it). To find something out, the answer must lie somewhere else in the region (a place, another person, a secret or a clue): the one who asked never teaches it, unless it is their own story; the step names what to learn in plain words. **Not now** simply lets a favour go (no penalty), walking away while they are still asking lets it go too, and a favour you have not finished lapses when you leave the region.

The card stays while you keep playing (typing something else does not answer it) and goes away if the party walks on; it is not shown while a Trouble ahead warning or a fight is on, and it comes back if you reload the page. When you first arrive in a region, the journal also gets **leads** for people elsewhere in it: *Someone at Thornwood Shrine may need help.* Go there to hear them out; the lead disappears once they ask.

**Leaving a region.** Regions are one-way: once you cross from a region's last place into the next region, you cannot go back. If you still have offered or active side quests there, the game asks first, on the phone of the player who proposed the trip: *Crossing into <region> leaves these behind: <quests>. Go on?* Say no and the party stays. Say yes and the party crosses; tasks whose steps were all done complete and pay as usual, and the rest are closed as **left behind**: no penalty, no lost goodwill, they just stay unfinished in the journal. The same happens to the tasks of a region you had already left before this rule existed (older saves), and to an offered quest whose giver lives in a region you have left (they can no longer ask you).

### The finale
When the master of the last region is dealt with, the story is not quite over: the party chooses how it ends. The story closes on a question (for example: silence the old song for good, or let its last verse be sung), and every phone with a hero shows the **finale card** at the top of the Play tab with that question and the **two endings** as buttons (on the other tabs a slim line, *The story waits for your choice*, with a **Choose** button). Pressing an ending asks *Are you sure? This ends the story.* with **Yes, end the story** and **Back**; nothing is decided until someone presses Yes, and the first player to confirm decides for the party, so talk it over first. Until then you can keep playing: walk around, rest, talk to people (no new quests are offered and no new danger starts while the card is open), and the card comes back if you reload the page. If you start a fight meanwhile (say, by attacking the master you made peace with), the fight comes first: the card hides and returns once it is over. Once an ending is chosen the story tells it, the Scribe says farewell and the **epilogue** follows: it tells only what really happened, including the ending you chose, how each region was resolved and by which way (by force, by the way of peace, or with a cunning plan first, told by the steps you really did, such as *the party won the fight at The Slag Warren*), and the people you met. It always closes on the game's own record, written by the engine and not the storyteller: who fell and who lived on, the **main quests** with how each ended, then your other quests and favours by outcome (completed, failed, left behind, let go or never taken up). A master you won over *sided with the party* and is never told as defeated or laid low: allies stay in their own place, and the party is always your heroes. Adventures from before this rule (or one written without a finale) end as soon as the last region is resolved, as they always did.

### What now?
Not sure what to do? Press **What now?** in the Now card on the **Play** tab, or type *what now* (also *what should we do*, *where to*, *I'm lost*, *help me*). The game answers at once from what you already know, in a few short lines: the main quest's ways you have found, each with its current step and where to go (a place, *two places away via* the next place on the way, or *3 of 4 places seen* while exploring), the current step of each task you took on and where, who is waiting for your answer, and your leads (while the finale card is open, it answers with the finale question). A quest item hidden somewhere is never given away beyond what the step itself says (*It is hidden there: search when you arrive.*). When nothing else is open, it may point you to someone who knows another way past the region's master, or list the places next to you that you have not seen. The answer opens in a panel on your phone (**Dismiss** closes it) and shows on the screen as a small *What now?* card. It does **not** take your turn, does not wait in the action queue and asks the storyteller nothing, so it works during a fight too. Asking again within a few seconds answers only your phone.

### Your hero's sheet
The **Hero** tab shows each fact once. Its picture is your portrait with your race, class and background; under it a row with your level and experience (and **Level up** when it is ready). **Overview** has speed, initiative, proficiency and passive Perception (hit points and armour class are on your hero strip at the bottom), abilities and saving throws, skills, attacks (to hit and damage), your features with their action and uses left (Second Wind: *Bonus action*, *1/1 short rest*), conditions when you have any, and your training (armour and weapons, tools, languages). **Inventory** shows your gold, the weight you carry and the party's camp supplies, the gear you wear as labelled slots (armour, main hand, shield or off hand, ranged) and your pack as a grid of slots with counts. Tap a slot to see the item and its buttons: **Use** (a potion, on yourself or a party member), **Equip** or **Unequip**, **Give** (to a person here) and **Drop**. **Spellbook** shows your slots and spells, and for a wizard the scrolls you carry that can be copied, each with its cost and a **Copy** button (outside a fight). Gear changes wait until a fight ends. In a fight potions and combat gear are used from the hotbar's **Items** (see Using your gear).

## 4. Combat

### How a fight is laid out
There is no grid. The battlefield is a handful of **zones** (a bridge, a courtyard, a ledge), joined by edges that have a distance in feet: **25 feet** between zones outdoors and **15 feet** indoors (caves, crypts, keeps), so every hero can reach the next zone and still act. Moving inside a zone is free. Moving to another zone costs the distance of the edge, and **twice as much** if the zone you enter is rough ground. You can only move as far as your speed allows each turn.

The screen shows the battlefield as a **hex map**: every zone is a hexagon, and **zones whose hexagons touch are next to each other** (one move apart); zones that do not touch are not. Each hex shows a picture of the place, its name and size, icons for **half cover**, **three-quarters cover**, **high ground** and **rough ground**, any surfaces on it (fire, grease, ice, a web... with the rounds they have left) and the creatures standing in it. On a big screen the icons carry their names; on a smaller one only the icons show, and the legend under the map names every icon in the fight and says how far apart touching zones are. A fight's map has three to six zones in at most two rows; the hex of the creature whose turn it is glows gold. A surface such as grease, ice or a web makes its zone rough ground while it lasts, so entering it costs double. Each zone in your phone's **Move** list shows the same cover, high ground, rough ground and surface badges. On your phone, target chips show each creature's zone and how far away it is.

Three things about where you stand:
- **Range** works in zones. A range of 10 feet or less (melee, touch, self) means the same zone. Up to 60 feet reaches one zone away, and anything longer reaches two zones away. Shooting beyond a weapon's normal range is done at disadvantage.
- **Cover**: a ranged attack from another zone into a zone with half cover gives the target +2 AC, and three-quarters cover gives +5 AC. Melee and same-zone attacks ignore cover.
- **High ground**: when you attack from high ground and the target is not on it, you have advantage. A ranged attacker below a target on high ground has disadvantage. In the same zone, nothing changes.
- **Darkness**: in a fight in a cave or crypt every zone is dark unless lit. A hero without darkvision attacks a target standing in a dark zone at disadvantage (*Darkness*); monsters see in the dark. A torch or lantern carried by a hero lights that hero's zone and the zones touching it, and the light moves with its bearer; every hero carrying a light lights their own zone. A candle lights only its own zone. Lighting one in a fight costs a bonus action, even when the zones around you are already lit. Burning fire lights the zone it is in.

### Dice in a fight
In a fight every roll plays on the hex map, one after another, and the story waits for them. An attack's die arcs from the attacker to the target and lands with its number; the verdict floats over the target, then the damage dice and the damage taken, while the target's health bar drains. A save or check drops a die over the creature that rolled it. When two creatures side by side get a verdict at once, the words sit next to each other, never over a zone's name. Under the map a strip spells out the action being shown (who at whom, the die and the maths, the verdict). In the side column **THIS ROUND** keeps one line per roll, newest on top, and empties when a new round begins.

The words are always told from the party's side: the die's colour says who rolled (steel teal for a hero, crimson for a monster) and the verdict's colour says what it means for the party (teal good, crimson bad). A monster that makes its save against you reads **RESISTED** (crimson); one that fails reads **CAUGHT** (teal). A monster's attack on a hero reads **MISSED** *hero* (teal) or **HIT** *hero* (crimson).

Out of a fight, healing, damage and other rolls that are not checks or saves still appear as big dice in the screen's side column for a few seconds.

### Starting a fight yourself
If you attack someone you were talking to (*I swing my hammer at the tollkeeper*), the game first asks **Are you sure?**. When you confirm, the fight starts with them in your zone, and the attack you named is rolled at once as the **opening strike**, before anyone's turn (as in the video game): your weapon, or a spell with an attack roll such as Eldritch Blast or Fire Bolt (a leveled spell uses its slot as usual). Someone who dies in a fight stays dead: they are gone from the place and cannot be talked to or fought again. The screen tells what really happened. Then initiative is rolled and you still get your normal turn. Creatures that turn up to fight (an ambush, a monster) start one zone away instead. When several foes in one fight share a name, each gets a letter (**Goblin A**, **Goblin B**) on the board, in the turn order and in the story, so you always know which one acted.

### Initiative and turns
At the start of a fight everyone rolls initiative: a d4 plus the Dexterity modifier (as in the video game). The turn order appears on the screen. If a side was surprised, its creatures lose their first turn. Heroes who are down keep their place in the order. The screen always names whose turn it is (**It is Goblin's turn**) and lights them in the turn order; each monster's turn is held on the screen for a moment (about a second and a half) so the table can follow what it did. The moment you end your turn your phone stops showing **Your turn**; the story of what happened is told while the next hero already plays.

### Your turn
When it is your turn, your phone says **Your turn** (with the time left when a turn timer runs, for example **Your turn - 2:41**) and the hotbar is active. Each turn you have:
- one **action**, one **bonus action** and one **reaction** (shown on the hotbar),
- **movement** up to your speed in feet,
- the option to type a creative action in the Play box and press **Act**. It uses your action, and it is refused once your action is spent.
- When something you typed changes nothing because the game refused it, the story says why in one line (*That does not happen: ...*), never a bare filler line.

The reaction is shown for completeness, but no reaction abilities work in this version.

**The turn timer.** Nobody's turn is taken away unexpectedly:
- At a **solo table** (only one player seated with a hero) there is **no turn timer**: take as long as you like.
- With several players the default is **3 minutes** per turn. The host can set it to **Off**, **90 seconds**, **3 minutes** or **5 minutes** in the Host panel.
- When a timer runs, your phone counts down (**Your turn - 2:41**) and the screen shows **Sam is acting - 0:45**.
- **30 seconds** before the end your phone says **30 seconds left: act or end your turn**.
- If the time runs out, the game plays a careful turn for you: it moves toward your allies if you are away from them, or else takes the Dodge action, and then ends your turn. With the timer **Off**, or at a solo table, this never happens while you are connected.
- If your phone loses its connection, your turn waits **30 seconds** for you to come back (reconnecting gives you your turn and your clock back). After that, or when your turn comes up while you have been away longer, the game plays the same careful turn for you.

### The hotbar
- Each button is a slot with its picture and its name under it, in rows by kind (attacks, actions, bonus actions, class features). Buttons are numbered. On a keyboard, **keys 1 to 9** use the numbered slots on your turn, and **Esc** cancels an aim.
- A slot with a **cyan** frame is the one you picked; an attack slot with a **red** frame says **Out of range** for the target you chose.
- Pick a **target chip** (name and health: Unhurt, Wounded, Bloodied, Fallen, Fled). Attacks then show your **chance to hit** and the chance of a critical hit against that target's armour class, and whether you have advantage or disadvantage. Spells with an attack roll (Eldritch Blast, Fire Bolt, ...) show their chance too, in the spell list, and the chip shows your best chance; it says **Out of range** only when neither a weapon nor such a spell can reach.
- Sections: **Attacks**, **Spells**, **Actions**, **Bonus actions**, **Items** and **Class features**.

### Attacks

Arrows and bolts are not counted: a bow or crossbow never runs out of ammunition (as in the video game this table is modelled on). Damage lines say so when immunity, resistance or vulnerability changed a hit (*is immune to acid damage (10 rolled, 0 taken)*), and a heal that adds a bonus to its die shows both (*regains 8 HP (now 8) (die 5 + bonus 3)*, the Life domain bonus).
An attack roll is a d20 plus your attack bonus against the target's armour class (AC). A natural 1 always misses. A natural 20 is a critical hit and doubles the damage dice. A fighter with Improved Critical crits on a lower number.
- Fighters and rangers attack more than once per action once they have **Extra Attack** (level 5). Your first attack spends the action and leaves the others available.
- An **off-hand attack** with a second weapon is a bonus action. It adds no positive ability bonus to damage unless you have the Two-Weapon Fighting style.
- **Close combat**: a ranged attack (a bow, a crossbow, a thrown weapon or a ranged spell attack) has disadvantage while a foe who can see you and can still act stands in your zone, whatever you aim at. Monsters shoot under the same rule. Fight hand to hand, or step out first.
- **A line with several acts in a fight** does each in turn while your turn lasts: *I charge the zombie and cleave it with my longsword* moves, then attacks; *I use Action Surge and swing at the sahuagin again* uses it, then attacks. A move followed by something else (*I run to the ravine and hide*) is the move, then that as your creative action.
- **Typing an attack** is the same attack: *I swing my longsword at the bandit*, *I cut down the spider with my sword*, *I jab the sahuagin in the ribs with my rapier*, *I loose an arrow at the mephit with my shortbow*. It rolls against the target's AC with your weapon's own damage, or the rules say plainly why it cannot happen (out of reach, no attack left). Any wording works when the line names a foe of the fight and a weapon: one of yours (*I run the thug through with my longsword*, *Elowen lets fly with her shortbow at the fungus*, *I hammer the Duke again with my longsword*) or a kind of weapon (*I put an arrow in the zombie's chest* is your bow or crossbow, *I hack at him with my big sword* your melee weapon). A trip or a shove (*I trip the thug with my sword*), a throw, or showing or putting away a weapon stays a creative action. A spell you name is cast, however it is said (*Tamsin hits the zombie with a Guiding Bolt*). A creative action never deals a weapon's damage in place of an attack: when your words strike with a weapon, the engine makes the weapon's attack roll (a thrown weapon is its throw).
- A rogue's **Sneak Attack** adds extra damage once per turn with a finesse or ranged weapon when you have advantage, or when an ally who can act is next to the target and you do not have disadvantage. It is 1d6 at level 1, 2d6 at level 3 and 3d6 at level 5.

### Other actions
To move, use the **Move** list right under the Now card on your phone (on your turn; its heading shows the feet you have left) and tap a zone. Each zone shows its distance from you (or "here") and the same facts as the board: cover, high ground, rough ground and any surfaces with their rounds left. A zone you cannot reach with the movement you have left is greyed out and says what it needs: **Dash first** (Dash doubles your movement for the turn) or **too far this turn**. You can also type it: *I move to the ravine*, *I run to Old Kern* (to the zone they stand in) or *I dash to the gully* (Dash first if needed). Moving does not use your action. You go by the cheapest way. Standing up from prone costs half your speed. These are the other actions on the hotbar:
- **Dash**: adds your speed again to your movement this turn.
- **Disengage**: has no effect in this version: leaving an enemy never provokes a free attack.
- **Dodge**: attacks against you have disadvantage until the start of your next turn.
- **Hide**: roll Stealth against the best Perception of the standing enemies. You stay hidden until you attack.
- **Help** (action): an ally in your zone gets advantage on their next attack or check. Helping an ally who is down gets them back up with 1 hit point.
- **Throw** (action): hurl a carried object at a foe in your zone or the next one (1d4 damage). It leaves your pack, hit or miss: a thrown weapon lands at this place (pick it up after the fight), anything else is gone.
- **Shove** (bonus action): in your zone, knock a foe prone or push them to another zone. They can be at most one size larger than you, they roll Athletics or Acrobatics (the better one) and you must beat that.
- **Jump** (bonus action): leap to a neighbouring zone, ignoring rough ground. It still uses movement equal to the distance, and you cannot jump while prone.
- **Flee** (no action, uses the rest of your movement): leave the fight. With an enemy in your zone you must **Disengage** first (the Flee button then says **Disengage first**); after Disengage you can flee in the same turn. You are then out of the fight. If everyone else falls, the party counts as having fled rather than as defeated.
- **Use item**: in a fight you drink a potion yourself as a bonus action. Outside a fight you can give one to another hero from the sheet. Drunk at full health it is wasted (gone, with no special effect); it is refused (and nothing is used) only for a dead hero.

### Spells and slots
Pick **Spells**, choose a spell, then choose its target or the zone. Casting a spell uses your action or bonus action depending on the spell. A bonus-action spell does not stop you from casting an action spell on the same turn.
- **Cantrips** cost nothing. They get stronger at character level 5.
- Levelled spells use a **slot** of that level (or a higher one for a stronger effect). Slots come back on a long rest. Warlock pact slots come back on a short rest too.
- **Concentration**: you can concentrate on one spell at a time, and casting another concentration spell ends the first. It also ends if you are knocked out or incapacitated, or if you fail a Constitution save. You make that save each time you take damage, against a DC of 10 or half the damage, whichever is higher.
- Area spells hit everyone in the target zone, **friends included** (never the caster). While you pick the zone, each zone in the **Move** list says who the spell would catch, with friends marked **(ally)**, or **Out of reach**.
- A cone, line or cube that starts from you (Burning Hands and Color Spray 15 ft, Thunderwave 15 ft, Fear 30 ft, Lightning Bolt 100 ft) is aimed: pick your own zone or a neighbouring zone whose distance is no longer than the spell (Burning Hands reaches a zone 15 ft away, not one 25 ft away; Fear reaches 25 or 30 ft). It hits everyone in that one zone and never you. Aimed at your own zone it also catches the friends beside you. Spirit Guardians always surrounds you in your own zone. One damage roll counts for all, and each target saves on their own.
- Spell attacks use your proficiency bonus plus your casting modifier.
- **Typing a spell in a fight** works like the hotbar: *I cast magic missile at the sahuagin*, *Rook casts burning hands on the violet fungus*, or with no cast word, naming a spell you have ready, *I call down sacred flame on the zombie*. The engine casts it: the slot (or daily use) is spent and the real attack roll or saving throw is made at your real spell DC. The target is the foe or friend you name (*me* is you); an area spell goes to the zone you name, or to the zone of the foe you name. Class abilities aimed at others work the same way: *I raise my holy symbol and use Turn Undead on the ghoul*. If the line names no valid target (*I cast fire bolt*), your phone says so (*Name who Fire Bolt is aimed at*) and nothing is spent. If the target is out of reach, the rules say why, the same as the hotbar.
- **Healing outside a fight**: type it, *I cast cure wounds on Tamsin* (Cure Wounds, Healing Word, Mass Healing Word, Prayer of Healing). The spell is cast by the engine with your lowest fitting slot, and the target heals; with no one named it heals you (a many-target spell heals the whole party). A spell you do not have, or no slot left, is refused in plain words.
- **Other spells outside a fight**: type it, *Elowen casts bless on Rook and Tamsin*, *I cast guidance*. A spell you type outside a fight always uses its slot (or its daily use; a cantrip uses nothing): the engine casts it, never the story alone. A spell that needs no fight (no attack roll, saving throw, damage or area) is cast on you or on the heroes you name (no one named: on you), with your lowest fitting slot. A spell aimed at a place rather than a creature (*I cast misty step to reach the roof*, *I cast fog cloud*) is cast where you stand: the slot is spent and the story tells the casting, but outside a fight it carries no one to another place (travelling is still travelling) and nothing it makes lasts. A harmful spell aimed at scenery or at nothing (*I cast burning hands at the empty reeds*, *I cast thunderwave out over the water*) is cast the same way and strikes no one, also when people stand near. A spell you do not have ready, or no slot left, is refused in plain words and nothing is cast. A harmful spell aimed at someone standing here (by name, by what they are, *the ferryman*, or as *him* or *her*), or at a foe waiting for your answer, and any spell aimed at another person here, goes to the storyteller as before (it may start a fight). You do not need the word *cast*: naming a spell you have ready works the same (*I murmur a healing word over Rook*).

### Class features
**On the hotbar** (you use them):
- **Second Wind** (fighter): bonus action, heals 1d10 plus your level, once per short rest.
- **Typing a feature or a heal in a fight**: on your turn, *I use Second Wind*, *I drink my potion of healing* or *I cast cure wounds on Tamsin* does exactly what the hotbar button does and costs the same (action, bonus action, use, slot or draught); if the rules refuse it, the reason is shown. A feature aimed at others (a breath weapon) is used from the hotbar.
- **Typing an attack in a fight**: on your turn, *I swing my longsword at the goblin*, *I stab the mephit with my rapier* or *I bring my mace down on the wolf* is rolled against armour class like the hotbar's attack, with that weapon. If the weapon you name is in your pack but not in your hand, your hero draws it as part of the attack, for free, and then attacks.
- **Action Surge** (fighter): gives one extra action, once per short rest.
- **Cunning Action** (rogue): Dash, Disengage or Hide as a bonus action (under Bonus actions).
- **Channel Divinity: Turn Undead** (cleric): turns undead creatures nearby.
- **Breath Weapon** (dragonborn).

**Automatic** (they just work):
- **Arcane Recovery** (wizard): on your first short rest after a long rest, you regain spent slots that add up to half your wizard level (rounded up), highest first, none higher than 5th.
- **Dark One's Blessing** (warlock fiend): temporary hit points when you drop a foe.
- The halfling's **Lucky** (a natural 1 is rerolled once) and the half-orc's **Savage Attacks**.

Some features appear on the sheet but cannot be used at the table yet; they are marked with an asterisk in the class table below. Three choices can be picked but do nothing yet: the fighting style **Protection**, and the ranger's **Giant Killer** and **Horde Breaker**.

### Features by level

<!-- generated:class_features -->
| Class | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
| --- | --- | --- | --- | --- | --- |
| Fighter | Fighting Style, Second Wind | Action Surge | Martial Archetype, Improved Critical | Ability Score Improvement | Extra Attack |
| Rogue | Expertise, Sneak Attack, Thieves' Cant | Cunning Action | Roguish Archetype, Fast Hands, Second-Story Work* | Ability Score Improvement | Uncanny Dodge* |
| Wizard | Spellcasting, Arcane Recovery, Scroll Copying | Arcane Tradition, Evocation Savant, Sculpt Spells* | - | Ability Score Improvement | - |
| Cleric | Spellcasting, Divine Domain, Domain Spells, Bonus Proficiency, Disciple of Life | Channel Divinity, Channel Divinity: Turn Undead, Divine Domain Feature, Channel Divinity: Preserve Life* | Domain Spells | Ability Score Improvement | Domain Spells, Destroy Undead* |
| Ranger | Favored Enemy*, Natural Explorer* | Fighting Style, Spellcasting | Ranger Archetype, Primeval Awareness*, Hunter's Prey | Ability Score Improvement | Extra Attack |
| Warlock | Otherworldly Patron, Pact Magic, Pact Slot Recovery, Dark One's Blessing | Eldritch Invocations* | Pact Boon* | Ability Score Improvement | - |

An asterisk marks a feature that is on the sheet but that the table cannot use yet.
<!-- end generated:class_features -->

### Surfaces
Spells, fire, oil and the like leave **surfaces** in a zone. Surfaces act when you enter them or at the start of your turn. They are shown on the board. A surface that lasts a number of rounds ticks down; the rest stay until removed.

<!-- generated:surfaces -->
| Surface | Lasts | Effect |
| --- | --- | --- |
| Fire | 3 rounds | on entering, at the start of a turn: 1d4 fire damage |
| Oil | until removed | rough ground (entering costs double movement) |
| Rubble | until removed | rough ground (entering costs double movement) |
| Grease | 10 rounds | rough ground (entering costs double movement); when it appears, on entering, at the start of a turn: DEX save DC 12, prone on a failed save |
| Caltrops | until removed | rough ground (entering costs double movement); on entering: DEX save DC 15, 1 piercing damage on a failed save |
| Ball Bearings | until removed | rough ground (entering costs double movement); on entering: DEX save DC 10, prone on a failed save |
| Water | until removed | no effect of its own |
| Ice | until removed | rough ground (entering costs double movement); on entering, at the start of a turn: DEX save DC 10, prone on a failed save |
| Poison Cloud | 3 rounds | on entering, at the start of a turn: CON save DC 12, 1d6 poison damage and poisoned for 1 round on a failed save |
| Steam | 2 rounds | no effect of its own |
| Web | until removed | rough ground (entering costs double movement); when it appears, on entering, at the start of a turn: DEX save DC 12, restrained while inside on a failed save |
| Fog | until removed | when it appears, on entering, at the start of a turn: blinded while inside |
| Magical Darkness | until removed | when it appears, on entering, at the start of a turn: blinded while inside |
| Stinking Cloud | until removed | when it appears, on entering, at the start of a turn: blinded while inside; at the start of a turn: CON save DC 12, nauseated for 1 round on a failed save |
| Sleet Storm | until removed | rough ground (entering costs double movement); when it appears, on entering, at the start of a turn: blinded while inside; on entering, at the start of a turn: DEX save DC 12, prone on a failed save |
| Silence | until removed | when it appears, on entering, at the start of a turn: silenced while inside |
| Spike Growth | until removed | rough ground (entering costs double movement); on entering: 4d4 piercing damage |
| Spirit Guardians | until removed | only hurts the caster's enemies; moves with the caster; on entering, at the start of a turn: WIS save DC 12, 3d8 radiant damage, half damage on a success |
<!-- end generated:surfaces -->

Surfaces can combine:

<!-- generated:surface_mixes -->
- Fire meets Oil: Oil is used up; DEX save DC 12, 2d6 fire damage, half damage on a success
- Oil takes fire damage: becomes Fire; DEX save DC 12, 2d6 fire damage, half damage on a success
- Fire meets Grease: Grease is used up; DEX save DC 12, 2d6 fire damage, half damage on a success
- Grease takes fire damage: becomes Fire; DEX save DC 12, 2d6 fire damage, half damage on a success
- Fire meets Web: Web is used up; 2d4 fire damage
- Web takes fire damage: Web is used up; 2d4 fire damage
- Water takes lightning damage: CON save DC 12, 1d4 lightning damage and shocked for 1 round on a failed save
- Water takes cold damage: becomes Ice
- Fire meets Water: becomes Steam
- Fire meets Ice: becomes Steam
- Water takes fire damage: becomes Steam
- Ice takes fire damage: becomes Steam
- Fire meets Sleet Storm: Fire is used up
<!-- end generated:surface_mixes -->

### Conditions
Conditions are shown on tokens and on your sheet.

<!-- generated:conditions -->
| Condition | What it does |
| --- | --- |
| Blinded | Its attacks have disadvantage; attacks against it have advantage; cannot see. |
| Charmed | Cannot attack whoever charmed it. |
| Deafened | No numbers of its own: the Dungeon Master plays it out. |
| Exhaustion | Its ability checks have disadvantage; lasts until a long rest. |
| Frightened | Its attacks have disadvantage; its ability checks have disadvantage. |
| Grappled | Cannot move. |
| Incapacitated | Cannot take actions; cannot take reactions. |
| Invisible | Its attacks have advantage; attacks against it have disadvantage; others cannot see it. |
| Paralyzed | Attacks against it have advantage; melee hits against it are critical hits; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Petrified | Attacks against it have advantage; automatically fails STR/DEX saves; cannot move; resists all damage; immune to poison damage; also counts as incapacitated. |
| Poisoned | Its attacks have disadvantage; its ability checks have disadvantage. |
| Prone | Its attacks have disadvantage; melee attacks against it have advantage; ranged attacks against it have disadvantage. |
| Restrained | Its attacks have disadvantage; attacks against it have advantage; disadvantage on DEX saves; cannot move. |
| Stunned | Attacks against it have advantage; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Unconscious | Attacks against it have advantage; melee hits against it are critical hits; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Dodging | Attacks against it have disadvantage; advantage on DEX saves; lasts 1 round. |
| Hidden | Its attacks have advantage; attacks against it have disadvantage; others cannot see it; ends after its next attack. |
| Surprised | Cannot move; cannot take actions; cannot take reactions; lasts 1 round. |
| Helped | Its attacks have advantage; its ability checks have advantage; ends after its next attack; lasts 1 round. |
| Blessed | 1d4 on attack rolls; 1d4 on saving throws. |
| Shield of Faith | +2 AC. |
| Chilled | Speed is 67%. |
| Shocked | Cannot take reactions. |
| True Strike | Its attacks have advantage; ends after its next attack. |
| Guided | Attacks against it have advantage. |
| Mage Armor | +3 AC. |
| Blurred | Attacks against it have disadvantage. |
| Invisibility | Its attacks have advantage; attacks against it have disadvantage; others cannot see it; ends after its next attack. |
| Slowed | Speed is 50%; cannot take reactions; -2 AC. |
| Nauseated | Cannot take actions; cannot take reactions; lasts 1 round. |
| Guidance | 1d4 on ability checks. |
| Resistance | 1d4 on saving throws. |
| Bane | -1d4 on attack rolls; -1d4 on saving throws. |
| Longstrider | +10 ft speed. |
| Barkskin | AC is at least 16. |
| Poison Ward | Resists poison damage. |
| Hunter's Mark | The caster's weapon hits on it add 1d6. |
| Expeditious Retreat | Can dash as a bonus action. |
| Asleep | Ends when it takes damage; also counts as unconscious. |
| Silenced | Immune to thunder damage; cannot cast spells with spoken parts; also counts as deafened. |
| Turned | Cannot take actions; cannot take reactions; ends when it takes damage; also counts as frightened. |
| Befriended | Cannot attack whoever charmed it; ends when whoever caused it, or one of their companions, harms it; also counts as charmed. |
| Burning | Takes 1d4 fire damage at the start of its turns; an action and a DC 10 DEX check end it; lasts 10 rounds. |
| Acid Burn | Takes 2d4 acid damage at the end of its turn; lasts 1 round. |
| Surrendered | Cannot move; cannot take actions; cannot take reactions; ends when whoever caused it, or one of their companions, harms it. |
<!-- end generated:conditions -->

### Suggestions
When it is another hero's turn, you can **suggest a move** to them (not during a monster's turn). It is only a hint: they decide. The suggestion appears on their phone. You can also type something creative for your own turn in the free-text box (**Or describe something creative**), and the game works out what it means.

### Monster behaviour and loot
Monsters have a fixed number of hit points. The host can scale monster health and damage (see For the host). Each defeated foe adds to the loot of the fight, and the experience of every defeated foe is split evenly among the living heroes.

### Demanding surrender
On your turn you can call on the foes to give up: *I call for them to surrender*, *drop your weapons*, *yield and we spare you*. It takes your action and is one roll: Intimidation, or Persuasion when you offer mercy (*spare*, *plead*, *promise*, *convince*). The difficulty is the same as talking your way past trouble in that region (easy in the first region, medium after that), one step harder while none of them has fallen and they still have more than half their strength. On a success every foe still standing **surrenders**: it drops its weapons and cannot attack, move or react. Undead, constructs, oozes and plants never surrender; they fight on. When every foe still standing is one of those, there is no roll: your phone says so plainly (*The Tithekeeper will not yield: the dead do not surrender.*) and you keep your action. When only some are, the roll counts for the others, and your phone names the ones that will not yield. A surrendered foe stays surrendered until a hero strikes it (an attack, a spell or an action); fire or oil the party set before it gave up can still burn it, and that does not end the surrender. When every foe left has surrendered or been befriended, the fight ends in victory, and surrendered foes count as beaten: they give experience and their loot, and a region's master who surrenders is dealt with as if defeated. On a failure nothing changes but your action.

### Ending a fight
A fight ends in **victory** when no hostile creature is left standing, in **defeat** when no hero can act, or when the party has fled. A foe your party has **befriended** (Animal Friendship on a beast, Charm Person on a person) no longer keeps a fight going: when only befriended foes are left, the fight ends as a victory. They are not defeated, so they give no experience and no loot. The charm ends as soon as the caster or any hero harms them. When a fight ends, effects that last a number of rounds end, and the story continues. The screen's **VICTORY!** banner and the victory music play only after a real victory, never after a defeat or an escape.

## 5. Spells and levelling

### Spell slots by level
Casters get more cantrips, spells and slots as they level up.

<!-- generated:spell_slots -->
| Class | Level | Cantrips | Spells known | Spell slots |
| --- | --- | --- | --- | --- |
| Wizard | 1 | 3 | prepared | L1: 2 |
| Wizard | 2 | 3 | prepared | L1: 3 |
| Wizard | 3 | 3 | prepared | L1: 4, L2: 2 |
| Wizard | 4 | 4 | prepared | L1: 4, L2: 3 |
| Wizard | 5 | 4 | prepared | L1: 4, L2: 3, L3: 2 |
| Cleric | 1 | 3 | prepared | L1: 2 |
| Cleric | 2 | 3 | prepared | L1: 3 |
| Cleric | 3 | 3 | prepared | L1: 4, L2: 2 |
| Cleric | 4 | 4 | prepared | L1: 4, L2: 3 |
| Cleric | 5 | 4 | prepared | L1: 4, L2: 3, L3: 2 |
| Ranger | 1 | 0 | 0 | none |
| Ranger | 2 | 0 | 2 | L1: 2 |
| Ranger | 3 | 0 | 3 | L1: 3 |
| Ranger | 4 | 0 | 3 | L1: 3 |
| Ranger | 5 | 0 | 4 | L1: 4, L2: 2 |
| Warlock | 1 | 2 | 2 | 1 pact slots of level 1 |
| Warlock | 2 | 2 | 3 | 2 pact slots of level 1 |
| Warlock | 3 | 2 | 4 | 2 pact slots of level 2 |
| Warlock | 4 | 3 | 5 | 2 pact slots of level 2 |
| Warlock | 5 | 3 | 6 | 2 pact slots of level 3 |
<!-- end generated:spell_slots -->

### Levelling up
- The game goes up to **level 5**. The experience you need: 300 for level 2, 900 for level 3, 2,700 for level 4 and 6,500 for level 5. Experience keeps counting after that.
- When you have enough, the phone shows **Level up!** and the Hero tab shows **Choose level-up options**. A level-up is always your choice: it never happens by itself. During a fight it waits: the Hero tab says **A new level waits: choose it when the fight is over** (as in the video game).
- In the dialog you pick what your class asks for at that level: a new path (subclass) at the right level, new spells (and for a known-spell caster, one spell may be swapped), and at level 4 an **ability score improvement**: +2 to one ability or +1 to two, never above 20.
- Your maximum hit points rise by a fixed average for your hit die (half the die plus one) plus your Constitution modifier, and your current hit points rise by the same amount, but levelling does not heal you to full. A hero who is down or dead cannot level up.
- Spell slots you already spent stay spent when your slots grow.
- A wizard adds two spells to their spellbook per level.
- **Prepared spells grow, they are never re-picked.** The spells you have prepared stay prepared; the level only adds room (your spellcasting modifier plus your new level, so an ability score improvement to Intelligence or Wisdom counts at once). A wizard's new room is filled with the spells just written into the spellbook, then with the rest of the book; a cleric picks spells for the new room.

### Spell list

<!-- generated:spells -->
| Spell | Level | School | Casting time | Range | Concentration | Classes |
| --- | --- | --- | --- | --- | --- | --- |
| Acid Splash | Cantrip | conjuration | action | 60 ft | no | wizard |
| Chill Touch | Cantrip | necromancy | action | 120 ft | no | warlock, wizard |
| Eldritch Blast | Cantrip | evocation | action | 120 ft | no | warlock |
| Fire Bolt | Cantrip | evocation | action | 120 ft | no | wizard |
| Guidance | Cantrip | divination | action | touch | yes | cleric |
| Poison Spray | Cantrip | conjuration | action | 10 ft | no | warlock, wizard |
| Ray of Frost | Cantrip | evocation | action | 60 ft | no | wizard |
| Resistance | Cantrip | abjuration | action | touch | yes | cleric |
| Sacred Flame | Cantrip | evocation | action | 60 ft | no | cleric |
| Shocking Grasp | Cantrip | evocation | action | touch | no | wizard |
| Spare the Dying | Cantrip | necromancy | action | touch | no | cleric |
| True Strike | Cantrip | divination | action | self | yes | warlock, wizard |
| Animal Friendship | 1 | enchantment | action | 30 ft | no | ranger |
| Bane | 1 | enchantment | action | 30 ft | yes | cleric |
| Bless | 1 | enchantment | action | 30 ft | yes | cleric |
| Burning Hands | 1 | evocation | action | self | no | wizard |
| Charm Person | 1 | enchantment | action | 30 ft | no | warlock, wizard |
| Color Spray | 1 | illusion | action | self | no | wizard |
| Cure Wounds | 1 | evocation | action | touch | no | cleric, ranger |
| Expeditious Retreat | 1 | transmutation | bonus action | self | yes | warlock, wizard |
| False Life | 1 | necromancy | action | self | no | wizard |
| Fog Cloud | 1 | conjuration | action | 120 ft | yes | ranger, wizard |
| Grease | 1 | conjuration | action | 60 ft | no | wizard |
| Guiding Bolt | 1 | evocation | action | 120 ft | no | cleric |
| Healing Word | 1 | evocation | bonus action | 60 ft | no | cleric |
| Hideous Laughter | 1 | enchantment | action | 30 ft | yes | wizard |
| Hunter's Mark | 1 | divination | bonus action | 90 ft | yes | ranger |
| Inflict Wounds | 1 | necromancy | action | touch | no | cleric |
| Longstrider | 1 | transmutation | action | touch | no | ranger, wizard |
| Mage Armor | 1 | abjuration | action | touch | no | wizard |
| Magic Missile | 1 | evocation | action | 120 ft | no | wizard |
| Shield of Faith | 1 | abjuration | bonus action | 60 ft | yes | cleric |
| Sleep | 1 | enchantment | action | 90 ft | no | wizard |
| Thunderwave | 1 | evocation | action | self | no | wizard |
| Acid Arrow | 2 | evocation | action | 90 ft | no | wizard |
| Aid | 2 | abjuration | action | 30 ft | no | cleric |
| Barkskin | 2 | transmutation | action | touch | yes | ranger |
| Blindness/Deafness | 2 | necromancy | action | 30 ft | no | cleric, wizard |
| Blur | 2 | illusion | action | self | yes | wizard |
| Darkness | 2 | evocation | action | 60 ft | yes | warlock, wizard |
| Hold Person | 2 | enchantment | action | 60 ft | yes | cleric, warlock, wizard |
| Invisibility | 2 | illusion | action | touch | yes | warlock, wizard |
| Lesser Restoration | 2 | abjuration | action | touch | no | cleric, ranger |
| Misty Step | 2 | conjuration | bonus action | 30 ft | no | warlock, wizard |
| Prayer of Healing | 2 | evocation | minutes | 30 ft | no | cleric |
| Protection from Poison | 2 | abjuration | action | touch | no | cleric, ranger |
| Scorching Ray | 2 | evocation | action | 120 ft | no | wizard |
| Shatter | 2 | evocation | action | 60 ft | no | warlock, wizard |
| Silence | 2 | illusion | action | 120 ft | yes | cleric, ranger |
| Spike Growth | 2 | transmutation | action | 150 ft | yes | ranger |
| Web | 2 | conjuration | action | 60 ft | yes | wizard |
| Fear | 3 | illusion | action | self | yes | warlock, wizard |
| Fireball | 3 | evocation | action | 150 ft | no | wizard |
| Hypnotic Pattern | 3 | illusion | action | 120 ft | yes | warlock, wizard |
| Lightning Bolt | 3 | evocation | action | self | no | wizard |
| Mass Healing Word | 3 | evocation | bonus action | 60 ft | no | cleric |
| Revivify | 3 | conjuration | action | touch | no | cleric |
| Sleet Storm | 3 | conjuration | action | 150 ft | yes | wizard |
| Slow | 3 | transmutation | action | 120 ft | yes | wizard |
| Spirit Guardians | 3 | conjuration | action | self | yes | cleric |
| Stinking Cloud | 3 | conjuration | action | 90 ft | yes | wizard |
<!-- end generated:spells -->

## 6. When a hero falls

### Zero hit points
When a hero drops to 0 hit points they fall unconscious and start **dying**. Monsters and companions who reach 0 hit points die immediately.

If a single hit leaves damage over after reaching 0 that is at least your maximum hit points, you die at once.

### Death saves
At the start of each of your turns while dying, you roll a d20 against a **DC of 10**:
- 10 or more: one success. Under 10: one failure.
- A natural 20: you get up with 1 hit point. A natural 1 counts as two failures.
- **Three successes** and you are **stable**: still at 0 hit points and out cold, but no longer rolling. **Three failures** and the hero **dies**.
- Taking damage while at 0 is one failure (two for a critical hit). Damage that is at least your maximum hit points kills outright.
- Healing a dying hero brings them back up and clears their counts. Healing spells, potions, the **Help** action (up with 1 hit point) and **Spare the Dying** (which stabilises) all work. **Revivify** brings back a hero who has died.
- Death saves are only rolled in a fight. When a fight ends and the party has not lost, every dying hero becomes **stable** (no more death saves; the counts reset).
- **Helping a hero up outside a fight**: a hero who is down stays down until someone raises them. Any standing hero can help them up with 1 hit point, for free: press **Help <name> up** on the Play tab (it appears on every standing hero's phone while an ally is down), or type it ("I help Mira up", "wake Mira", "help her up"). A potion, a healing spell or a short rest works too. The downed hero's phone says so.

While you are down, your phone says **You are down**. Your companions carry on.

### A hero who has died
A dead hero is out of the story unless the party revives them. Outside a fight, **the Scribe** can do it for gold (see The Scribe).

### Defeat
The party is defeated when every hero is dead, or when no hero can act (all at 0 hit points or dead) and no ally can help. The screen shows **Defeat** and the checkpoint it will return to, and phones are locked. **The host** (or the only player) chooses:
- **Retry from the last checkpoint**: the game goes back to the last checkpoint (the moment you arrived somewhere, or the start of a fight). The dice are rolled again, so the same fight can end differently.
- **Load a save**: pick a saved campaign.
- **New adventure**: start over.

Checkpoints are made automatically whenever the party arrives somewhere (unless arriving starts a fight) and when a fight starts. The newest 10 are kept.

## 7. The Scribe

### Who he is
The Scribe is a quiet keeper of a ledger in which every tale is written. He speaks rarely, in a warm, calm and gently amused voice, and he believes some tales may yet be amended. He has no fixed place; he is there when the table needs him.

### When he speaks
A welcome of about a minute as soon as the host presses **Start the adventure** (he keeps the table company while the world is being written; the opening narration waits until he is done), a welcome back when a saved adventure is loaded, a brief line when a hero is rewritten, and a farewell when the campaign is won. He appears and speaks only on the shared screen, for the whole group; phones never show or play him. While he speaks, the story waits and the music fades out; it fades back in when he is done. He stays silent after an ordinary fight; the screen just shows **Victory!**. The host can press **Skip the Scribe** in the Host panel, and anyone can press **Skip** on the screen. If he refuses a request, his reason is shown as text on the Scribe tab of your phone.

### Rewriting a fallen hero
On the **Scribe** tab you can see fallen heroes (dead heroes, not ones at 0 hit points who are still alive). A standing hero pays the Scribe to rewrite a fallen hero into the story. Rules:
- Only **outside combat**.
- The price is **25 gp per level** of the fallen hero.
- **The fallen hero's own purse pays first**; you pay the rest from your own hero's gold (the card shows the split, for example **50 gp from Mira's purse, 0 gp from you**). You must be standing yourself.
- The rewritten hero comes back with **half of their maximum hit points** (rounded up), their death saves reset and their conditions cleared (exhaustion stays).

<!-- generated:scribe_prices -->
| Level of the fallen hero | Price |
| --- | --- |
| 1 | 25 gp |
| 2 | 50 gp |
| 3 | 75 gp |
| 4 | 100 gp |
| 5 | 125 gp |
<!-- end generated:scribe_prices -->

### When he says no
- A fight is under way, the party has been defeated, or the game is paused.
- Nobody has fallen.
- The hero you chose has not fallen (a hero at 0 hit points who is alive is not fallen).
- Your own hero is down: a standing hero must pay.
- The fallen hero's purse and your gold together are not enough.

Nothing is spent on a refusal.

## 8. For the host

### Starting and hosting
- Start the server with the LAN option so phones can join. Add the HTTPS option to enable the microphone button. The first browser to join becomes the host. The role follows the people at the table: in the lobby it moves at once to the next player when the host leaves; during an adventure the host keeps it while away for up to 60 seconds (a sleeping phone), then it moves to the player who joined earliest among those connected. A loaded save gives it to the first player to connect if the old host does not come back. A former host who returns is an ordinary player.
- Windows may ask whether Python may accept connections: allow it on private networks.
- The game needs a DeepSeek key for the live Dungeon Master and a Fish Audio key and voice for spoken narration, both optional. Spoken narration starts switched off: turn on **Spoken narration** in the Host panel. Without keys the game still plays with a built-in fallback storyteller.

### Host controls
Open **More**, then **Host panel** (only the host sees it).
- **Pause the game / Resume the game**: no turns or actions are handled while paused. A turn whose timer runs out while paused gets a fresh timer; an open vote keeps running.
- **Force the open vote**: pass the current vote.
- **Kick**: remove a player (asks first).
- **Monster health** and **Monster damage** multipliers: from x0.25 to x3. The health change applies to monsters that appear from then on.
- **Turn timer**: the time each hero has for a combat turn: **Off**, **90 seconds**, **3 minutes** (the default) or **5 minutes**. It only runs when another player is waiting, so a solo table never has one. A change applies to the current turn at once and is saved with the game.
- **Spoken narration**: switch the voice on or off.
- **Save now**, **Load**, **New campaign** and **End the session**. Loading or starting new saves the current game first.
- **Storyteller usage**: the number of calls and tokens used.
- After a defeat, only the host (or a lone player) chooses what happens.

### Saves
The game saves as it goes (every event is logged), into a folder per campaign. A saved campaign is restored exactly as it was, including your heroes and the story. Saves live on the host's computer, never in the cloud.

## 9. Reference and troubleshooting

The tables in this manual are written by the game from its data. Races, classes, backgrounds, class features, spell slots, conditions, surfaces, spells, items and prices are all there above.

### Troubleshooting
- **The page will not open on my phone**: check that you are on the same Wi-Fi, use the address from the screen, and ask the host to allow the game through the firewall on private networks.
- **A certificate warning**: with the HTTPS option this is normal once per browser. Choose Advanced, then continue.
- **No Dictate button**: it only appears over HTTPS (or on the host's own computer) in a browser with speech input. Use your keyboard's dictation key.
- **No sound**: sound plays only on the shared screen. Click the screen's page once (**Click anywhere to start the table's sound**), then check the Screen sound volume and mute on the More tab or the screen's gear. No spoken narration: the host must turn on **Spoken narration** in the Host panel (and the host's computer needs a Fish Audio key and voice).
- **"The storyteller lost the thread"**: the live AI is not answering. The game uses plain fallback telling and keeps going. Press **Dismiss**.
- **"Tonight the table plays a prepared adventure"**: the live AI could not write a campaign in time, so the built-in one is played. Narration is still live; nothing is wrong.
- **I closed the page**: open the game address again in the same browser; it reconnects you to your hero.
- **"This table was restarted. Join again to take a seat."**: the server was restarted since this page joined. Press **Join**.
- **Someone else is the host**: the first player in is the host. If that player has left, the role moves to the next player by itself (at once in the lobby, after 60 seconds during an adventure).
- **My hero is down and I cannot act**: ask a companion to help you up (outside a fight the **Help <name> up** button on their phone, in a fight the Help action), to heal you, or to take a short rest. The Scribe only helps heroes who have died.
