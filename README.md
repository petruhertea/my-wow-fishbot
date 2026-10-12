# python-fishbot

A small computer-vision project that plays the fishing mini-game in World of Warcraft (retail) by
**looking at the screen**: it finds the bobber, watches it, and reels in when a fish bites.

It is built to work together with the **[Avid Angler](https://www.curseforge.com/wow/addons/avid-angler)
addon**: the bot presses **Ctrl+F**, and Avid Angler is what actually casts and reels in (and, if you
configure it to, applies baits and other buffs). The bot's job is the part the addon can't do: seeing
where the bobber is and noticing the bite.

It was started from a YouTube tutorial (screen capture + template matching) and grew into something
that copes with different zones, lighting and water colours.

> ## ⚠️ Read this first
> Blizzard's Terms of Use prohibit bots and any automation of gameplay. **Using this program can get
> your account suspended or banned.** This repository is shared as a computer-vision learning
> project. You are responsible for what you do with it. See [Risks](#risks-and-responsibility)
> before running anything.

---

## Contents

- [How it works (plain English)](#how-it-works-plain-english)
- [Requirements](#requirements)
- [Install](#install)
- [Game setup checklist](#game-setup-checklist)
- [Running it](#running-it)
- [Settings you can change](#settings-you-can-change)
- [Debug output](#debug-output)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Risks and responsibility](#risks-and-responsibility)
- [Project layout](#project-layout)

---

## How it works (plain English)

The bot never touches the game's memory or files. It only takes screenshots (about 15–20 per
second), looks at them with OpenCV, and moves the mouse / presses keys like a person would.

One cast goes through these steps:

1. **Look at the empty water first.** A few screenshots are taken *before* casting. Anything that
   already moves (leaves, a forge's bellows, shimmering reflections) is marked as "ignore".
2. **Cast** (the bot presses Ctrl+F, which Avid Angler turns into a cast) and wait for the bobber to land and settle.
3. **Find the bobber.** Three methods are tried, from most to least trusted:
   - **Template match** – compares the screen to a small picture of the bobber's feathers. It is only
     accepted if it is a very close match (0.85+), because the bobber's colours change with the
     zone and the time of day, so a close match is a bonus, not something to rely on.
   - **New red feather** – the main method. The feather is red, and water usually isn't. The bot
     looks for red pixels that were **not** there before the cast. If several red shapes show up
     (the feather and the thin red fishing line), it picks the **lowest** one, because the line
     runs *up* from the bobber.
   - **Frame difference** – last resort. Finds "what changed between the before and after
     screenshots". It doesn't care about colour, but it can be fooled by anything that moves.
4. **Move the mouse onto the bobber** and learn what it looks like at rest for one second. The bobber
   bobs gently, so "at rest" is a wobble, not a still picture.
5. **Wait for a bite.** A bite is a **sudden jump** in how much the area around the bobber changes
   (the bobber dips and splashes). The slow bobbing waves are ignored because they never rise
   fast. When a jump is confirmed, the bot presses Ctrl+F again, which Avid Angler turns into reeling in.
6. If nothing happens within 20 seconds, it recasts.

Why each piece exists:

| Problem | What solves it |
|---|---|
| Bobber colours change with zone / lighting / fog | Don't depend on one colour picture; find *new red* and *what changed* instead |
| Trees, forges and water reflections move on their own | Record a few frames before casting and ignore everything that already moves |
| The fishing line is red too and can be mistaken for the bobber | Pick the lowest red shape, ignore thin streaks |
| A fixed "bite" level gets crossed by the bobber's own bobbing | Look for a sudden jump instead of a high level, adapted to this bobber's wobble |
| Keys sent while another window is focused (e.g. VS Code's Find box) | Only send keys while the WoW window is active (Windows) |
| Windows display scaling mismatches mouse and screenshot coordinates | Use 100% scaling (see setup) |

---

## Requirements

- Windows (screen capture uses `PIL.ImageGrab`, and the "is WoW focused?" check uses the Windows API)
- World of Warcraft **retail**, **1920×1080**, full screen or borderless, on your **primary monitor**
  (the screen capture grabs the primary display only)
- Windows display scaling **100%**
- The **Avid Angler** addon, with its fishing action bound to **Ctrl+F**
- Python as specified in `pyproject.toml` and [uv](https://docs.astral.sh/uv/)

## Install

```powershell
git clone https://github.com/petruhertea/my-wow-fishbot.git
cd my-wow-fishbot
uv sync
```

## Game setup checklist

- [ ] Resolution **1920×1080**, full screen or borderless window
- [ ] Windows display scaling **100%** (Settings → System → Display → Scale). At 125% the mouse
      lands in the wrong place even if detection is perfect
- [ ] **First-person camera, UI hidden** (Alt+Z). Fewer moving things means fewer false detections
- [ ] Camera aimed so the water fills the lower part of the screen (the search area is the water
      only, see `SEARCH_ROI`)
- [ ] **Avid Angler** installed and its fishing action bound to **Ctrl+F**. The bot sends that one key
      for both casting and reeling in; Avid Angler does the rest. Set up baits and buffs in the
      addon's own options if you want them. If you use a different key or addon, change the key in
      `fishing_agent.py` (`pyautogui.hotkey('ctrl', 'f')`, used when casting and in `pull_line`)
- [ ] Stand still, out of combat, on calm open water. Combat interrupts fishing

## Running it

```powershell
uv run python-fishbot
```

That is the standard way: `uv run` makes sure the environment is ready and runs the `python-fishbot`
command defined in `pyproject.toml`, which calls `main()` in `src/python_fishbot/__init__.py`.
These do the same thing if you prefer them:

```powershell
uv run python -m python_fishbot
uv run -m python_fishbot
```

### Double-click launcher (Windows)

`fishbot.bat` in the project folder does the same thing without opening an editor: it switches to its
own folder, checks that `uv` is installed, runs `uv run python-fishbot` and keeps the window open so you
can read any error. Double-click it, or make a shortcut to it.

Then, in the terminal:

| Key | Action |
|---|---|
| `S` | Start the screen capture (do this first) |
| `F` | Start the fishing agent (you get 5 seconds to click on the WoW window) |
| `Q` | Quit (from the menu, so stop the fishing agent first) |

**Emergency stop:** press `Ctrl+C` in the terminal (it returns you to the menu), or throw the mouse
into a screen corner (PyAutoGUI's fail-safe).

## Settings you can change

Everything is at the top of `src/python_fishbot/fishing/fishing_agent.py`:

| Setting | What it does |
|---|---|
| `SEARCH_ROI` | Rectangle `(x0, y0, x1, y1)` the bot searches. Keep it on the water: raise `y0` so buildings, trees and the shoreline are excluded |
| `SCREEN_OFFSET` | Only if you capture a cropped game window instead of the full screen |
| `DEBUG` | Saves images and logs for every cast. Turn it off for long sessions (see below) |
| `WINDOW_TITLE` | Window title the focus guard looks for (`World of Warcraft`) |

Bite sensitivity lives in `BiteDetector` (`lure_detector.py`): the smallest jump that counts
(`min_jump`, default 10) and how long it must stay up (`sustain`, default 0.1 s).

## Debug output

With `DEBUG = True`, each cast creates `debug/attempt_NNN/` with:

- `before.png`, `after.png`, `diff.png` – what the bot saw
- `result.png` – the detected spot circled in green; the **yellow rectangle is the search area**
- `motion_excluded.png` – what it ignored because it was already moving
- `deltas.csv` – the bite signal over time
- `summary.txt` – detector used, bite or not, how big the biggest jump was

and one row per cast is added to `debug/attempts.csv` (outcome `BITE`, `NO_BITE` or `NOT_FOUND`).

Two things to know:

- **Disk space:** every cast saves several full-size PNGs (roughly several MB per cast). A long
  session adds up, so turn `DEBUG` off once things work. `debug/` should not be committed to git.
- **Privacy:** screenshots can contain chat text, character and guild names, and anything else on
  your screen. Look through them before sharing them.

## Troubleshooting

| What you see | Likely cause | Try |
|---|---|---|
| Cursor goes somewhere in the sea, nowhere near the bobber | Detection picked something else | Open `result.png`: is the circle on the bobber? Tighten `SEARCH_ROI`; make sure scaling is 100% |
| Cursor goes to buildings / trees / scenery | Search area includes moving scenery | Raise `y0` in `SEARCH_ROI` so only water is searched |
| Cursor lands on the bobber but no reel-in | Bite not detected | Look at `max_jump` in `attempts.csv`: if it is 6–9 on missed bites, lower `min_jump` |
| Line is pulled at random moments | Bite threshold too sensitive | Raise `min_jump` / `sustain` |
| `NOT_FOUND` over and over | Bobber not visible or no new red | Check `after.png`; reduce clutter (UI off, first person); red liquids are hard (see limitations) |
| Mouse is off by a consistent distance | Display scaling ≠ 100%, or a cropped capture | Set scaling to 100% or use `SCREEN_OFFSET` |
| "WoW isn't the active window" | Another window has focus | Click on the game window; the bot waits |
| Nothing happens in game when the bot "casts" or "reels" | Ctrl+F isn't bound to Avid Angler, or WoW isn't focused | Check the binding in WoW and in the addon; click on the game window |
| First cast does strange things | The game window wasn't focused at the start | Use the 5-second countdown to click into WoW |

## Known limitations

- Windows only, retail only, 1920×1080 only (other resolutions need `SEARCH_ROI` and patch sizes
  adjusted).
- **Red liquids** (e.g. blood pools) can hide the red feather, because only *new* red pixels count.
  Frame difference is then the fallback, and it is weaker.
- Very busy water (lava, bubbling liquids) raises the bobber's resting wobble and makes bite
  detection less reliable.
- Camera movement between the before and after screenshots confuses the frame-difference fallback.
- Reeling and casting happen at fairly regular intervals; the bot does not try to look human.
- It does not handle combat, full bags, dismounting, dying or being talked to. Avid Angler's own options
  (baits, buffs) are outside what this project controls.

## Risks and responsibility

**Account risk.** Blizzard's Terms of Use forbid bots and any automation of gameplay, and Blizzard
has banned very large numbers of accounts for it in the past, from temporary suspensions to
permanent bans. This bot only reads the screen and presses keys, which is different from bots that
read the game's memory, but the rule is about automation itself. Nobody can promise it won't be
detected. If you can't afford to lose the account, don't run it.

**About Avid Angler.** The addon describes itself as working within Blizzard's addon restrictions:
you press a key and it does the next step. That design assumes a person is pressing the key. In
this project the key presses are generated by the bot, so the automation is done by this program,
not by the addon, and the addon's own rules do not cover that. This project is not affiliated with
Avid Angler.

**Risks to your character while you're away from the keyboard.**

- Mobs, other players or events can attack you. On a PvP realm you may get ganked.
- Being in combat stops fishing; the bot does not notice or react.
- Full bags, a loot window, a dialogue or a disconnect all leave the bot casting into nothing.
- Other players can report an obvious bot. A character that fishes for hours without a break looks
  like one.

**Risks to your computer.**

- The bot sends real key presses and mouse movements. If another window gets focus (the Windows
  guard only covers the check "is WoW active", not every situation), keys can land somewhere you
  didn't intend. Don't leave it running on a machine you can't see.
- Mouse control means you can't use the computer normally while it runs.
- Debug images can contain private information (see above).

**What this project is not.** It is not endorsed by or affiliated with Blizzard Entertainment.
World of Warcraft is a trademark of its owner. Use it at your own risk; the author takes no
responsibility for bans, lost progress or anything else that follows from running it.

## Credits

- **[Avid Angler](https://www.curseforge.com/wow/addons/avid-angler)** – the WoW addon that does the
  casting, reeling in and (optionally) baits and buffs behind the Ctrl+F key. It makes this project
  much simpler than clicking the bobber with the mouse would. Not affiliated with this project.
- **[OpenCV](https://opencv.org/)**, **[NumPy](https://numpy.org/)**, **[Pillow](https://python-pillow.org/)**
  and **[PyAutoGUI](https://pyautogui.readthedocs.io/)** – screen capture, image analysis and input.
- Started from **[PyGameBot](https://www.youtube.com/watch?v=TCzMkWkpMS4&list=PLClhiip1oU4pYFI9BUwP9ffCliXowczQj)**'s YouTube tutorial on screen capture and template matching.

## Project layout

```
fishbot.bat                  # double-click launcher (Windows)
src/python_fishbot/
├── __init__.py              # screen capture thread, command menu (S / F / Q) and main()
├── __main__.py              # lets you run `python -m python_fishbot`
└── fishing/
    ├── __init__.py          # (empty) marks this folder as a package
    ├── fishing_agent.py     # casting, bobber search, bite watching, logging
    ├── lure_detector.py     # template match, new-red, frame difference, bite detector
    ├── assets/              # small bobber pictures used by the template match
    └── img/                 # example screenshots
```