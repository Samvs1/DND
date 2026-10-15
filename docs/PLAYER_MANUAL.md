# Player Manual

Everything you need to play at the table, in plain words. The tables in the Reference part are written by the game from its own data, so they are always right. This manual is also inside the game: open the **More** tab on your phone and press **Player manual**, or open the page `/manual` on any screen.

## 1. Getting started

### What you need
- One computer runs the game and acts as the server. It is called the host's computer here.
- A TV or laptop shows the shared screen. Each player uses their own phone (or laptop) as a controller.
- Everyone must be on the same Wi-Fi network. The game is made for one to four players.
- A spoken narrator and music are optional. Without them the game still works, and the story appears as text.

### The two surfaces
- **The screen** (the page `/screen`) is the table everyone looks at: scene art, the story (with what each player typed), the party, the hex battle map, big dice, who is acting and who is waiting, votes, the narrator's voice and the music.
- **The phone** (the page `/play`, or just the game address) is your controller. It shows your hero and your buttons, not the story: the story is told on the screen. Its five tabs sit at the top, right under your hero: **Play**, **Hero**, **Journal**, **Scribe** and **More**. The square button next to your hero switches **full screen**, which hides the browser's own bars (on Android this stops a bottom toolbar from covering the game); it is also on the More tab.
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
- Only the shared screen plays sound: the narrator, the Scribe and the music. Phones are silent. Spoken narration plays only when the host has switched **Spoken narration** on in the Host panel and the host's computer has a Fish Audio key and voice.
- On the **More** tab, the **Screen sound** section changes narrator volume, music volume and mute on the shared screen from your phone. Any seated player can do this, and the last change wins.
- The **Settings** button on your phone has text speed, text size and a reduce-motion switch. The screen's gear button has the sound settings for the screen.
- When the screen opens, it asks for one click (**Click anywhere to start the table's sound**) because browsers block sound until a page is clicked. It asks again if the browser blocks a clip. Click once and everything plays.

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
You get the gear your background lists and your class's starting kit, and your class lets you choose between a few packages. The wizard shows what each choice contains. You can change your equipment later on the Hero tab (outside fights).

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
- **The Now card** at the top says what is going on for you: *Your move*, *The story is being told. Watch the screen.*, whose action the Dungeon Master is weighing, your place in line, or that the game is paused. Under it: where you are and the objective of your active **main quest** (a side quest never shows here), with the **What now?** button beside it (see *What now?* below). The screen's header line shows the same main objective.
- **The action box** sits right under it.
- **Ideas**: chips built from the scene: **People here** (talk to someone), **Things here** (take a closer look at something, pick up an item), **Ways on** (travel to a connected place; a locked way is greyed out, and tapping it says why it is shut) and **Anytime** (look around, search, short rest, and **Trade** when a trader is here). Tapping a chip writes the sentence in the action box; it never sends by itself, so you can change it and press **Act**.
- **Your last roll** stays on the tab (label, dice, total and outcome); a short note also pops up when you roll.

**Everyone sees what you typed.** When your action starts to play out, the screen shows your words in the story as a small framed card with your hero's portrait, your name and your hero's name (**Ann as Brienne** *"I look inside the cabin"*); the storyteller's telling of what happened follows right under it. The same goes for a creative action or a typed move in a fight. Only *inventory* stays private: its answer goes to your phone alone, so the screen shows nothing for it. The cards stay in the story when the screen is reloaded or a saved adventure is loaded.

The story itself is not repeated on the phone. If you missed a line, open **Journal**, then **Story**: the recent story in full, newest at the bottom (what someone typed reads there as **Ann (Brienne):** "I look inside the cabin").

The Dungeon Master says as much as the moment is worth: a line or two for something small (a look around, small talk, a try that fails), two or three sentences usually, and a little more for big moments (a discovery, a fight starting or ending, a death, arriving somewhere new). It only tells what the game really did: if nothing changed, it describes your attempt, not a result.

The storyteller's prose reads as one paragraph. Plain statements from the game itself each get their own line, on the screen and in **Journal**, **Story** (*Slendee gains True Strike.*, *True Strike ends for Slendee.*, *2 Giant Rats are surprised.*). When someone you talk to answers, their words appear once, on their own line, after their name: **Warden Sellen Ost:** "Leave the lantern." The storyteller leaves the answer to them.

**Picking things up**: type *pick up the pouch* (or *take*, *grab*, *pocket* ...) or tap a **Things here** chip, and an item lying where you are goes into your pack at once; the screen says so in one short line. Things you find in the story that are not ordinary gear (a note, a key, a strange trinket) become **keepsakes**: you carry them, they have no price and cannot be sold, and they are listed under **Keepsakes** in your Hero tab's inventory.

**Quest items and keepsakes**: some things lie in the world because a quest needs them (the orders a smuggler lost, three ember-stones for a beacon). They are **quest items**: picked up, they become keepsakes that belong to a task, and they count for that task's steps. Like every keepsake they cannot be sold or dropped. Some lie in plain sight; others are hidden, and you find them by searching the place where they lie (type *I search the tunnels*; a Perception or Investigation check that is good enough turns them up). A plain keepsake from the story is just that: a memento with no use in any task, even if it looks like something a quest asks for. The storyteller cannot conjure a quest item out of thin air: if it lies elsewhere, you have to go and find it.

**Giving things**: on the **Hero** tab, every keepsake has a **Give** button: it opens the people here (alive and not hostile) and hands the keepsake to the one you pick (not during a fight). A quest item says *Quest item: for <quest>*, a plain keepsake says *Keepsake*. You can also type *give the tide-orders to Gorran* (or *hand*, *show*, *offer*; *give Gorran the orders* works too) while that person is here, and your hero really hands it over: a keepsake or quest item now belongs to them (that is how a quest step to deliver something is done), and an ordinary item from your pack is a gift they appreciate. Handing over a keepsake earns no favour by itself; finishing the task does. If the person is not here, is hostile, or you do not carry the thing, your phone says so and nothing changes.

### The action queue
Actions are handled one at a time, in the order they were sent. You may have one action waiting at a time. The screen shows who is typing, who is acting now and who is next. Your words appear in the story when your turn in line comes up, not while they wait. Your phone shows **Waiting (n)** while your action is in line. If the storyteller stumbles, you see a plain in-story fallback instead of an error.

### What the Dungeon Master can and cannot do
The storyteller describes the world and decides what happens, but it only does so by asking the game engine. **The engine owns every number**: difficulty, damage, hit points, spell slots, experience and gold. The storyteller cannot make up a damage total, hand out treasure beyond the rules, or invent things that were never introduced. Nor can it invent quests or quest items: tasks come from the story's people, and steps are checked off by the game (only a step that needs judgement, like calming a ghost, is ticked off by the storyteller); a person you meet who wants help asks a favour through the card. It does not tell you your next step unless you ask. If you try something clever, the engine rolls for it. Attacking someone who is not already hostile (a friendly or neutral person) asks you first (**Are you sure?**), because they will fight back. Nothing else asks. **Nothing happens until you answer**: the question stays on your phone until you press **Yes, do it** or **No, hold back** (the storyteller's voice does not close it), and the story only says that you hesitate on the brink. The attack is told once you confirm. Sending a new action instead counts as **No**.

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

- A natural 20 on an ability or skill check always succeeds and a natural 1 always fails.
- Saving throws compare the total only. Spell save DC is 8 + proficiency bonus + your casting modifier.
- **Advantage** means you roll two d20 and keep the higher. **Disadvantage** keeps the lower. They cancel each other out.
- Passive Perception is 10 plus your Perception bonus.
- The big dice on the screen show what was rolled, what it was against, and whether it was a success, failure or critical.

### Trouble ahead
When the party arrives somewhere dangerous, the game warns you first and nothing starts without a choice. Every phone with a hero shows a **Trouble ahead** box: who you face and how hard the fight looks (trivial to deadly). The first player to press a choice decides for the whole party:
- **Fight**: the fight begins.
- **Ambush them**: the whole party rolls Stealth. If at least half succeed, the foes are surprised. The fight starts either way.
- **Slip away**: each hero rolls the better of Stealth and Athletics. If at least half succeed, the party goes back to where it came from and there is no fight. If not, the fight begins.
- **Parley**: your hero (the one whose player pressed it) rolls Persuasion. On a success there is no fight. On a failure the fight begins.

The first place of each region is always safe. Fights start only from a warning you answer or from what the party does, never from a timer. The master of a region waits in its last place with company: foes from around the region who make it a hard fight.

### Votes
Some things need the whole table: **travelling**, **resting** (short or long) and **browsing a shop**. To ask, type it on the Play tab (*take a short rest*, *make camp* for a long rest, *go to* a place) or press **Trade** when a trader is here; a vote then opens on every phone (as a card at the top of the page) and on the screen. Typing *look around* or *inventory* gets an instant answer without a vote.
- Each player presses **Ready** or **Not yet**. The person who asked counts as ready.
- It passes as soon as more than half are ready and fails as soon as half or more decline.
- If time runs out (30 seconds), it passes when more are ready than declined. Silence does not block the table.
- Only connected players with a living hero vote. The host can press **Host: decide now** to force the open vote.

### The map and travel
The **Journal** tab has a **Map** section. It shows the region as places you can visit, with your current place marked and unexplored places in fog. Some places are locked until something happens in the story. Under **Travel**, each place connected to yours has a **Travel to** button: press it and the table votes. A locked way says why it is shut, under its button, when you tap its chip, and when you try to go there: a region's last place (where its master waits) *stays shut while <region> still hides places you have not seen: 2 left*, naming the places when you know the way to them, and the way into the next region *opens once the master of <region> is dealt with*. That is a fact of the world, not a hint. You cannot travel during a fight. Arriving may start a story scene, a warning (see Trouble ahead) or someone asking for help (see Quests and the journal). Crossing into the next region with unfinished side quests asks first (see Leaving a region).

### Rests
Rests also need a vote and happen between fights.
- **Short rest**: every living hero regains half of their maximum hit points (a hero at 0 HP wakes up), and abilities that come back on a short rest are restored. You can take at most two short rests between long rests.
- **Long rest**: every living hero returns to full hit points and regains all spell slots and abilities. Temporary hit points and short effects end, and death save counts reset. A long rest costs **10 camp supplies for each living hero**. If the party does not have enough, it is refused.
- **Camp supplies** are shared by the whole party. The party starts with 40. Buy rations, baskets, stew kits and hampers in shops, or find them as loot. Fallen heroes are not revived by resting and do not pay.

### Shops
When the table agrees to browse a shop, your phone opens the shop. Every player trades for themselves with their own gold.
- **For sale** lists what the trader sells. **Your pack** lists what you can sell.
- A trader sells different things depending on their trade.
- You cannot sell what you are wearing or wielding: take it off first.

<!-- generated:shop_rules -->
- You buy at 100% of an item's value, rounded up, never less than 1 gp.
- A shop buys from you at 50% of the value, rounded down.
- You can trade up to 10 of an item at a time.
- A trader whose trade is unclear counts as a general shop.

Kinds of shop:

- **General** sells gear, tool, supply, key, potion (about 14 items).
- **Smith** sells weapon, armor (about 14 items).
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
After a victory the party's loot is gathered into one reward: experience for every living hero, gold shared out evenly (any remainder goes to the first heroes), items handed out in turn, and any camp supplies found go to the shared pool. Gold is kept per hero and shows on your sheet. The adventure's main quests pay gold, experience and sometimes an item when they are completed; side quests that come up in play pay nothing by themselves. Reaching new places and clearing them can pay experience too.

### Quests and the journal
The **Journal** tab has three sections: **Journal**, **Map** and **Story** (the recent story in full, for catching up). The Journal section is laid out like this. At the top the **main quest** of the region is pinned: its title, its objective and every **way** you have found so far (Force, Peace, Cunning), each with the steps you have done ticked off; a way that is finished is marked *Done*. Under it the quests are grouped: **Active**, **Offered** (who asked, and the objective they told you), **Leads** (plain lines about rumours and hints of tasks still to be found), **Completed**, and **Left behind and failed** (greyed out and folded away; tap to open). Each quest card shows who gave it, the objective, its done steps ticked off and a short log of what happened in it (older log lines fold away). The journal shows what you have **done**, not what to do next: the next step is told only by the *What now?* help. It also keeps what is known so far and earlier scenes. On the phone, a short **toast** at the top tells the quest moments (a task taken on, a step done, a quest completed, a way found, a lead, a task left behind, a keepsake handed over), and the screen's story shows the same moments as lines. Each region has one **main quest**, active from the moment you arrive: it ends when the region's master is defeated, or when you finish another way of dealing with them that you discover by talking to the right people or by doing one of its steps. Quests are made of steps, and the game checks a step off by itself as soon as what it asks has really happened (you went there, won the fight there, carry the item, handed it over, met the person). Only the quest items the game placed for a task count for it; see *Quest items and keepsakes* above. Work you did before taking a quest on counts once it is active. An offered quest does not move until it is accepted; when every step of an accepted quest is done, it completes and pays its reward once.

**Quests come from people.** Nobody hands you a list. When the party arrives where someone needs help, that person asks (one ask per arrival): the story tells it, and every phone with a hero shows a card at the top of the Play tab, *<name> asks: <quest>*, with what they want and two buttons. The first player to answer decides for the party:
- **Accept**: the quest becomes active. Anything you already did for it counts at once.
- **Not now**: nothing is lost and nobody minds. The quest stays offered, and the card comes back the next time you arrive where that person is.

The full card shows on the **Play** tab. On the other tabs a slim line (*<person> asks: <quest>*) with an **Answer** button stays at the top and takes you back to Play, so it never covers your sheet or journal. **Give** opens its list of people right under the keepsake, with a **Cancel**.

**Favours.** Besides the quests of the story, someone you meet may ask a small favour of you (look in on a place, carry a keepsake to someone, find out something). It comes through the same card, with the same **Accept** and **Not now**. A favour has one step, the game checks it off like any other step, and only one favour can be open at a time (each person asks at most one). Doing it earns that person's goodwill, never gold, experience or items. **Not now** simply lets a favour go (no penalty), walking away while they are still asking lets it go too, and a favour you have not finished lapses when you leave the region.

The card stays while you keep playing (typing something else does not answer it) and goes away if the party walks on; it is not shown while a Trouble ahead warning or a fight is on, and it comes back if you reload the page. When you first arrive in a region, the journal also gets **leads** for people elsewhere in it: *Someone at Thornwood Shrine may need help.* Go there to hear them out; the lead disappears once they ask.

**Leaving a region.** Regions are one-way: once you cross from a region's last place into the next region, you cannot go back. If you still have offered or active side quests there, the game asks first, on the phone of the player who proposed the trip: *Crossing into <region> leaves these behind: <quests>. Go on?* Say no and the party stays. Say yes and the party crosses; tasks whose steps were all done complete and pay as usual, and the rest are closed as **left behind**: no penalty, no lost goodwill, they just stay unfinished in the journal. The same happens to the tasks of a region you had already left before this rule existed (older saves), and to an offered quest whose giver lives in a region you have left (they can no longer ask you).

### What now?
Not sure what to do? Press **What now?** in the Now card on the **Play** tab, or type *what now* (also *what should we do*, *where to*, *I'm lost*, *help me*). The game answers at once from what you already know, in a few short lines: the main quest's ways you have found, each with its current step and where to go (a place, *two places away via* the next place on the way, or *3 of 4 places seen* while exploring), the current step of each task you took on and where, who is waiting for your answer, and your leads. A quest item hidden somewhere is never given away beyond what the step itself says (*It is hidden there: search when you arrive.*). When nothing else is open, it may point you to someone who knows another way past the region's master, or list the places next to you that you have not seen. The answer opens in a panel on your phone (**Dismiss** closes it) and shows on the screen as a small *What now?* card. It does **not** take your turn, does not wait in the action queue and asks the storyteller nothing, so it works during a fight too. Asking again within a few seconds answers only your phone.

### Your hero's sheet
The **Hero** tab shows hit points, armour class, speed, initiative, proficiency, passive Perception, abilities, saving throws, skills, attacks, features, conditions and resources. Its **Inventory** section lets you equip, unequip, drop and use items. **Spellbook** shows your slots and spells. Gear changes wait until a fight ends. Potions are drunk from the hotbar in a fight.

## 4. Combat

### How a fight is laid out
There is no grid. The battlefield is a handful of **zones** (a bridge, a courtyard, a ledge), joined by edges that have a distance in feet: **25 feet** between zones outdoors and **15 feet** indoors (caves, crypts, keeps), so every hero can reach the next zone and still act. Moving inside a zone is free. Moving to another zone costs the distance of the edge, and **twice as much** if the zone you enter is rough ground. You can only move as far as your speed allows each turn.

The screen shows the battlefield as a **hex map**: every zone is a hexagon, and **zones whose hexagons touch are next to each other** (one move apart); zones that do not touch are not. Each hex shows a picture of the place, its name and size, icons for **half cover**, **three-quarters cover**, **high ground** and **rough ground**, any surfaces on it (fire, grease, ice, a web... with the rounds they have left) and the creatures standing in it. On a big screen the icons carry their names; on a smaller one only the icons show, and the legend under the map names every icon in the fight and says how far apart touching zones are. A fight's map has three to six zones in at most two rows; the hex of the creature whose turn it is glows gold. A surface such as grease, ice or a web makes its zone rough ground while it lasts, so entering it costs double. Each zone in your phone's **Move** list shows the same cover, high ground, rough ground and surface badges. On your phone, target chips show each creature's zone and how far away it is.

Three things about where you stand:
- **Range** works in zones. A range of 10 feet or less (melee, touch, self) means the same zone. Up to 60 feet reaches one zone away, and anything longer reaches two zones away. Shooting beyond a weapon's normal range is done at disadvantage.
- **Cover**: a ranged attack from another zone into a zone with half cover gives the target +2 AC, and three-quarters cover gives +5 AC. Melee and same-zone attacks ignore cover.
- **High ground**: when you attack from high ground and the target is not on it, you have advantage. A ranged attacker below a target on high ground has disadvantage. In the same zone, nothing changes.

### Starting a fight yourself
If you attack someone you were talking to (*I swing my hammer at the tollkeeper*), the game first asks **Are you sure?**. When you confirm, the fight starts with them in your zone, and the attack you named is rolled at once as the **opening strike**, before anyone's turn (as in the video game): your weapon, or a spell with an attack roll such as Eldritch Blast or Fire Bolt (a leveled spell uses its slot as usual). Someone who dies in a fight stays dead: they are gone from the place and cannot be talked to or fought again. The screen tells what really happened. Then initiative is rolled and you still get your normal turn. Creatures that turn up to fight (an ambush, a monster) start one zone away instead. When several foes in one fight share a name, each gets a letter (**Goblin A**, **Goblin B**) on the board, in the turn order and in the story, so you always know which one acted.

### Initiative and turns
At the start of a fight everyone rolls initiative: a d4 plus the Dexterity modifier (as in the video game). The turn order appears on the screen. If a side was surprised, its creatures lose their first turn. Heroes who are down keep their place in the order. The screen always names whose turn it is (**It is Goblin's turn**) and lights them in the turn order; each monster's turn is held on the screen for a moment (about a second and a half) so the table can follow what it did. The moment you end your turn your phone stops showing **Your turn**; the story of what happened is told while the next hero already plays.

### Your turn
When it is your turn, your phone says **Your turn** (with the time left when a turn timer runs, for example **Your turn - 2:41**) and the hotbar is active. Each turn you have:
- one **action**, one **bonus action** and one **reaction** (shown on the hotbar),
- **movement** up to your speed in feet,
- the option to type a creative action in the Play box and press **Act**. It uses your action, and it is refused once your action is spent.

The reaction is shown for completeness, but no reaction abilities work in this version.

**The turn timer.** Nobody's turn is taken away unexpectedly:
- At a **solo table** (only one player seated with a hero) there is **no turn timer**: take as long as you like.
- With several players the default is **3 minutes** per turn. The host can set it to **Off**, **90 seconds**, **3 minutes** or **5 minutes** in the Host panel.
- When a timer runs, your phone counts down (**Your turn - 2:41**) and the screen shows **Sam is acting - 0:45**.
- **30 seconds** before the end your phone says **30 seconds left: act or end your turn**.
- If the time runs out, the game plays a careful turn for you: it moves toward your allies if you are away from them, or else takes the Dodge action, and then ends your turn. With the timer **Off**, or at a solo table, this never happens while you are connected.
- If your phone loses its connection, your turn waits **30 seconds** for you to come back (reconnecting gives you your turn and your clock back). After that, or when your turn comes up while you have been away longer, the game plays the same careful turn for you.

### The hotbar
- Buttons are numbered. On a keyboard, **keys 1 to 9** use the numbered slots on your turn, and **Esc** cancels an aim.
- Pick a **target chip** (name and health: Unhurt, Wounded, Bloodied, Fallen, Fled). Attacks then show your **chance to hit** and the chance of a critical hit against that target's armour class, and whether you have advantage or disadvantage. Spells with an attack roll (Eldritch Blast, Fire Bolt, ...) show their chance too, in the spell list, and the chip shows your best chance; it says **Out of range** only when neither a weapon nor such a spell can reach.
- Sections: **Attacks**, **Spells**, **Actions**, **Bonus actions**, **Items** and **Class features**.

### Attacks
An attack roll is a d20 plus your attack bonus against the target's armour class (AC). A natural 1 always misses. A natural 20 is a critical hit and doubles the damage dice. A fighter with Improved Critical crits on a lower number.
- Fighters and rangers attack more than once per action once they have **Extra Attack** (level 5). Your first attack spends the action and leaves the others available.
- An **off-hand attack** with a second weapon is a bonus action. It adds no positive ability bonus to damage unless you have the Two-Weapon Fighting style.
- A rogue's **Sneak Attack** adds extra damage once per turn with a finesse or ranged weapon when you have advantage, or when an ally who can act is next to the target and you do not have disadvantage. It is 1d6 at level 1, 2d6 at level 3 and 3d6 at level 5.

### Other actions
To move, use the **Move** list right under the Now card on your phone (on your turn; its heading shows the feet you have left) and tap a zone. Each zone shows its distance from you (or "here") and the same facts as the board: cover, high ground, rough ground and any surfaces with their rounds left. A zone you cannot reach with the movement you have left is greyed out and says what it needs: **Dash first** (Dash doubles your movement for the turn) or **too far this turn**. You can also type it: *I move to the ravine*, *I run to Old Kern* (to the zone they stand in) or *I dash to the gully* (Dash first if needed). Moving does not use your action. You go by the cheapest way. Standing up from prone costs half your speed. These are the other actions on the hotbar:
- **Dash**: adds your speed again to your movement this turn.
- **Disengage**: has no effect in this version: leaving an enemy never provokes a free attack.
- **Dodge**: attacks against you have disadvantage until the start of your next turn.
- **Hide**: roll Stealth against the best Perception of the standing enemies. You stay hidden until you attack.
- **Help** (action): an ally in your zone gets advantage on their next attack or check. Helping an ally who is down gets them back up with 1 hit point.
- **Throw** (action): hurl a carried object at a foe in your zone or the next one (1d4 damage).
- **Shove** (bonus action): in your zone, knock a foe prone or push them to another zone. They can be at most one size larger than you, they roll Athletics or Acrobatics (the better one) and you must beat that.
- **Jump** (bonus action): leap to a neighbouring zone, ignoring rough ground. It still uses movement equal to the distance, and you cannot jump while prone.
- **Flee** (no action, uses the rest of your movement): leave the fight. With an enemy in your zone you must **Disengage** first (the Flee button then says **Disengage first**); after Disengage you can flee in the same turn. You are then out of the fight. If everyone else falls, the party counts as having fled rather than as defeated.
- **Use item**: in a fight you drink a potion yourself as a bonus action. Outside a fight you can give one to another hero from the sheet. It is refused (and nothing is used) if the hero is at full health or dead.

### Spells and slots
Pick **Spells**, choose a spell, then choose its target or the zone. Casting a spell uses your action or bonus action depending on the spell. A bonus-action spell does not stop you from casting an action spell on the same turn.
- **Cantrips** cost nothing. They get stronger at character level 5.
- Levelled spells use a **slot** of that level (or a higher one for a stronger effect). Slots come back on a long rest. Warlock pact slots come back on a short rest too.
- **Concentration**: you can concentrate on one spell at a time, and casting another concentration spell ends the first. It also ends if you are knocked out or incapacitated, or if you fail a Constitution save. You make that save each time you take damage, against a DC of 10 or half the damage, whichever is higher.
- Area spells hit everyone in the target zone, **friends included** (never the caster). Self-range areas such as Burning Hands, Thunderwave, Color Spray, Fear and Spirit Guardians use your own zone, and Lightning Bolt also hits the neighbouring zones. One damage roll counts for all, and each target saves on their own.
- Spell attacks use your proficiency bonus plus your casting modifier.

### Class features
**On the hotbar** (you use them):
- **Second Wind** (fighter): bonus action, heals 1d10 plus your level, once per short rest.
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
| Blinded | Its attacks have disadvantage; attacks against it have advantage. |
| Charmed | Cannot attack whoever charmed it. |
| Deafened | No numbers of its own: the Dungeon Master plays it out. |
| Exhaustion | Its ability checks have disadvantage; lasts until a long rest. |
| Frightened | Its attacks have disadvantage; its ability checks have disadvantage. |
| Grappled | Cannot move. |
| Incapacitated | Cannot take actions; cannot take reactions. |
| Invisible | Its attacks have advantage; attacks against it have disadvantage. |
| Paralyzed | Attacks against it have advantage; melee hits against it are critical hits; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Petrified | Attacks against it have advantage; automatically fails STR/DEX saves; cannot move; resists all damage; immune to poison damage; also counts as incapacitated. |
| Poisoned | Its attacks have disadvantage; its ability checks have disadvantage. |
| Prone | Its attacks have disadvantage; melee attacks against it have advantage; ranged attacks against it have disadvantage. |
| Restrained | Its attacks have disadvantage; attacks against it have advantage; disadvantage on DEX saves; cannot move. |
| Stunned | Attacks against it have advantage; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Unconscious | Attacks against it have advantage; melee hits against it are critical hits; automatically fails STR/DEX saves; cannot move; also counts as incapacitated. |
| Dodging | Attacks against it have disadvantage; advantage on DEX saves; lasts 1 round. |
| Hidden | Its attacks have advantage; attacks against it have disadvantage; ends after its next attack. |
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
| Invisibility | Its attacks have advantage; attacks against it have disadvantage; ends after its next attack. |
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
<!-- end generated:conditions -->

### Suggestions
When it is another hero's turn, you can **suggest a move** to them (not during a monster's turn). It is only a hint: they decide. The suggestion appears on their phone. You can also type something creative for your own turn in the free-text box (**Or describe something creative**), and the game works out what it means.

### Monster behaviour and loot
Monsters have a fixed number of hit points. The host can scale monster health and damage (see For the host). Each defeated foe adds to the loot of the fight, and the experience of every defeated foe is split evenly among the living heroes.

### Ending a fight
A fight ends in **victory** when no hostile creature is left standing, in **defeat** when no hero can act, or when the party has fled. When it ends, effects that last a number of rounds end, and the story continues. The screen's **VICTORY!** banner and the victory music play only after a real victory, never after a defeat or an escape.

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
