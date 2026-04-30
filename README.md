# Lumen

> Live captions & AI insights, on top of everything.

Lumen turns a transparent fullscreen layer into a meeting copilot. It
receives captions from a browser extension, streams them in front of
every other window, and — on a hotkey — asks Gemini to distil the
conversation into a HUD, a summary, action items, or open questions.

A modern dark-themed dashboard, a frameless click-through overlay with
glassmorphism, and a system-tray icon make it feel native on Windows 11.

---

## Quick start (Windows)

1. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/windows/) — make sure “Add to PATH” is ticked.
2. Double-click **`setup.bat`** once. This creates `.venv\` and installs everything.
3. Edit **`.env`** and paste your Gemini key:

   ```
   GEMINI_API_KEY=your_key_here
   ```

4. Double-click **`run.bat`**.

That's it. Lumen will appear in your system tray and the dashboard
will open. Click the tray icon any time to bring it back.

To see the live console log:

```
run.bat --visible
```

---

## What's in the dashboard

- **Live** — real-time transcript stream, status cards, and a quick-action bar:
  *Answer*, *Shorten*, *Recap*, *Follow-up*, *Define*, plus *Spotlight*. Export
  the transcript to Markdown anytime.
- **Context** — paste your resume, the role/JD, and any live notes. Everything
  here is folded into every Coach prompt.
- **Insights** — every analysis is archived and rewatchable.
- **Settings** — overlay, Coach panel opacity, auto-answer, hotkeys, default
  mode, Gemini model… all autosaved.
- **About** — keyboard shortcuts and version info.

## The Coach panel

A movable, resizable, semi-transparent panel that floats above every window.
Five quick actions:

| Mode         | What it does                                        |
| ------------ | --------------------------------------------------- |
| **Answer**   | 3–5 read-aloud bullets for the question just asked. |
| **Shorten**  | Tightens up your last reply.                        |
| **Recap**    | Summary of the conversation so far.                 |
| **Follow-up**| Sharp next questions to keep the thread alive.      |
| **Define**   | Defines the most jargon-y term just used.           |

You can also hit the **Spotlight** hotkey to ask anything ad-hoc — it's
answered against the live transcript and your resume/role context.

If **Auto-answer** is enabled in Settings, Lumen detects when a question is
asked (heuristic: ends in `?` or starts with *what / why / how / could you*…)
and fires *Answer* automatically.

## Default hotkeys

| Action                  | Key                    |
| ----------------------- | ---------------------- |
| Answer the latest thing | `0`                    |
| Spotlight (ask anything)| `Ctrl + Shift + Space` |
| Toggle captions overlay | `Ctrl + Shift + O`     |
| Stealth — hide all      | `Ctrl + Shift + H`     |
| Quit Lumen              | `Ctrl + Shift + Q`     |

All five are remappable from **Settings**.

## Caption ingest API

Lumen listens on `http://127.0.0.1:5000/api/captions` for JSON like:

```json
{ "speaker": "Alex", "text": "Let's reconvene Friday." }
```

Any browser extension or script that POSTs in this shape will populate
the overlay and the live dashboard.

A health probe is exposed at `http://127.0.0.1:5000/api/health`.

## Files Lumen creates

| File                    | Purpose                                  |
| ----------------------- | ---------------------------------------- |
| `lumen_settings.json`   | Persisted user preferences.              |
| `lumen_history.json`    | Last 50 AI analyses (mode, summary, ts). |
| `meet_captions.txt`     | Append-only raw transcript log.          |
| `context.txt` *(opt.)*  | Extra notes fed to Gemini as context.    |

## Running outside Windows

Lumen is Windows-first but the underlying stack is cross-platform:

```
python -m venv .venv
source .venv/bin/activate          # bash/zsh
pip install -r requirements.txt
python -m app.main
```

On macOS/Linux, the `keyboard` package usually requires `sudo` for
global hotkey registration; the rest of the app works without it.

## Architecture

```
app/
├── main.py              # entry — wires everything + StealthManager
├── server.py            # Flask caption endpoint + question detection
├── ai.py                # Gemini integration, all coach/text/HUD modes
├── overlay.py           # transparent click-through caption layer
├── overlay_render.py    # glassmorphism caption HTML templates
├── coach.py             # movable, resizable Coach suggestion panel
├── spotlight.py         # frameless spotlight quick-prompt
├── dashboard.py         # frameless modern dashboard (Live/Context/…)
├── styles.py            # Qt stylesheet (dark theme)
├── tray.py              # system tray menu
├── hotkeys.py           # global hotkey registration
├── config.py            # JSON-backed settings (incl. resume/role/notes)
└── state.py             # cross-thread Qt signal bus
```

Every UI update flows through a single `Bus` of Qt signals, so Flask,
the AI worker, the hotkey thread, and the Qt event loop never touch
each other's state directly.
