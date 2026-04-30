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

- **Live** — real-time transcript stream, status cards, and a one-click
  *Analyse with Gemini* button with four output modes.
- **Insights** — every analysis is archived and rewatchable.
- **Settings** — overlay position, font size, glass plate, default mode,
  Gemini model, hotkeys… all autosaved.
- **About** — keyboard shortcuts and version info.

## Default hotkeys

| Action            | Key                |
| ----------------- | ------------------ |
| Run analysis      | `0`                |
| Toggle overlay    | `Ctrl + Shift + O` |
| Quit Lumen        | `Ctrl + Shift + Q` |

All three are remappable from **Settings**.

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
├── main.py              # entry — wires everything together
├── server.py            # Flask caption endpoint
├── ai.py                # Gemini integration, multi-mode analysis
├── overlay.py           # transparent click-through window
├── overlay_render.py    # glassmorphism HTML templates
├── dashboard.py         # frameless modern dashboard
├── styles.py            # Qt stylesheet (dark theme)
├── tray.py              # system tray menu
├── hotkeys.py           # global hotkey registration
├── config.py            # JSON-backed settings
└── state.py             # cross-thread Qt signal bus
```

Every UI update flows through a single `Bus` of Qt signals, so Flask,
the AI worker, the hotkey thread, and the Qt event loop never touch
each other's state directly.
