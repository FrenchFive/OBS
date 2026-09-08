# OVERLAY 🎬

Two overlays for OBS — no server, no dependencies, just two HTML files you drop
into a **Browser source**. Made for a *Daily Journal* stream: a clean Apple-style
window around the camera, and a camcorder / surveillance HUD with the time of day
and the real recording data.

Everything they show is **real**: the recording timecode comes from OBS itself,
the battery is your computer's battery, the format chips and free disk space come
from OBS, the mic meter shows your real levels, and LIVE lights up when you go live.

| File | What it is |
|------|------------|
| [`frame.html`](frame.html) | **Apple window** — rounded bezel, hairline contour, macOS title bar with traffic lights, title, LIVE pill and the clock, home indicator |
| [`camera.html`](camera.html) | **Camcorder HUD** — `REC` + OBS recording timecode, `LIVE`, mic level meter, corner framing marks, real format / disk / battery, big clock + date, name and location |
| [`preview.html`](preview.html) | Local preview: both overlays over a fake camera picture |
| [`corner-mask.png`](corner-mask.png) | Alpha mask that rounds the camera itself, so the frame can drop its black bezel — see below (regenerate it from [`mask.html`](mask.html)) |

---
## 1. Turn on the OBS WebSocket server

Needed for the recording timecode and the LIVE indicator (it is **off** by default):

**OBS ▸ Tools ▸ WebSocket Server Settings ▸ Enable WebSocket server** → port `4455`.

If you set a password there, add it to the source URL: `?obspass=yourpassword`.
Without the server the overlays still work — the timecode just counts from the
moment the source loads, and LIVE stays unlit.

## 2. Add the sources

1. **Sources → + → Browser**
2. Tick **Local file** and pick `frame.html` (or `camera.html`)
3. **Width `1920` · Height `1080`**
4. Leave *Shutdown source when not visible* **off** so the clock keeps running
5. Repeat for the second file, and put **`camera.html` above `frame.html`** in the list

The overlays scale themselves, so they still look right if the source is resized.
Both are fully transparent — everything under them shows through.

> [!IMPORTANT]
> **OBS caches browser sources.** After editing one of these files, the source keeps
> showing the old page until you open its **Properties** and click
> **"Refresh cache of current page"** (or restart OBS). If something looks out of
> date — wrong FPS, a missing line — refresh the cache first.

> [!TIP]
> To use the URL parameters below, **untick "Local file"** and paste the path in the
> URL field instead, e.g.
> `file:///Users/chan/Documents/OBS/Overlay/camera.html?loc=Paris%2C%20FR&res=1080p`

---
## `frame.html` — the Apple window

| Param | Default | Meaning |
|-------|---------|---------|
| `title` | `Camera` | Title bar text |
| `sub` | `Session Log` | Small caption under the title (empty = hidden) |
| `live` | `auto` | `auto` = the pill appears while OBS is streaming · `1` = always · `0` = never |
| `clock` | `1` | Clock on the right of the title bar |
| `seconds` | `0` | Show seconds in that clock |
| `bezel` | `1` | Dark band + rounded corners over the video |
| `radius` · `margin` · `chrome` | `44` · `26` · `58` | Corner radius · bezel thickness · title bar height |
| `indicator` | `1` | iPhone-style home bar at the bottom |
| `vignette` | `1` | Subtle darkening of the edges |
| `accent` | `#ff453a` | LIVE dot colour |
| `obs` · `obshost` · `obsport` · `obspass` | `1` · `localhost` · `4455` · *(empty)* | obs-websocket connection |
| `locale` / `hour12` | `en-GB` / `0` | Date-time formatting |
| `preview` | `0` | Fake background, to check the design in a browser |

Example: `frame.html?title=Journal&sub=&accent=%2332d74b&bezel=0`

---
## `camera.html` — the camcorder HUD

| Param | Default | Meaning |
|-------|---------|---------|
| `name` | `FIVE Neo` | Signature, bottom right |
| `loc` | `auto` | `auto` = city + UTC offset read from the system clock · `off` · or your own text: `?loc=Paris%2C%20FR` |
| `tc` | `obs` | `obs` = **the real OBS recording time** · `elapsed` = counts from source load · `clock` = time of day |
| `rec` | `1` | REC indicator — red and blinking while OBS records, `STBY` when it doesn't, `PAUSE` when paused |
| `live` | `auto` | `auto` = lights up while OBS is streaming · `1` = always on · `0` = hidden |
| `battery` | `auto` | `auto` = your computer's battery (bolt while charging, red at ≤20%) · `off` · or a fixed number |
| `res` · `fps` | `auto` · `auto` | Format chips — `auto` reads OBS's real output size and frame rate (the FPS also sets the frames of the timecode). Pass your own text to pin them: `?res=4K&fps=60` |
| `disk` | `1` | Free disk space, read from OBS. Turns red under 10 GB |
| `meter` | `1` | Mic level meter under the REC indicator — real levels from OBS. Hidden until OBS sends any |
| `mic` | *(auto)* | Which input the meter follows. Empty picks your mic automatically; otherwise the exact input name: `?mic=Mic%2FAux` |
| `session` | `1` | `SESSION hh:mm:ss` since the source loaded |
| `brackets` · `ticks` | `1` · `1` | Corner framing marks · small edge marks |
| `focus` | `0` | Framing brackets in the centre of the picture |
| `scrim` | `55` | `0-100` — soft dark bands behind the top and bottom of the HUD, so the text stays readable on bright shots. `0` removes them |
| `shadow` | `100` | `0-200` — strength of the shadow under the text and the marks |
| `scan` | `0` | Faint CRT scanlines |
| `label` | *(empty)* | Caption centred at the top, e.g. `?label=Daily%20Journal` |
| `margin` · `top` · `bottom` | `112` · `140` · `112` | Safe area of the text blocks |
| `inset` · `topinset` | `62` · `104` | Position of the corner marks |
| `obs` · `obshost` · `obsport` · `obspass` | `1` · `localhost` · `4455` · *(empty)* | obs-websocket connection |
| `locale` / `hour12` | `en-GB` / `0` | `15:02:46` vs `3:02:46 PM` |
| `preview` | `0` | Fake background, to check the design in a browser |

Example: `camera.html?loc=Paris%2C%20FR&res=1080p&fps=60&scan=1`

---
## Preview outside OBS

Chrome blocks `file://` pages from embedding each other, so serve the folder:

```bash
python3 -m http.server 8931 --directory Overlay
```

Then open <http://localhost:8931/preview.html> — both overlays over a fake camera
picture. Add `?bg=light` to check readability against a bright, daylight room. Single overlays can also be opened straight from disk with `?preview=1`.

---
## Getting rid of the black border

The bezel is black **on purpose**: a browser source cannot cut a hole in the video
underneath it, so the only way to round the camera's corners is to paint over them.
Nest that scene somewhere else and the band shows up as a black border.

**The clean fix — round the camera itself, then turn the bezel off:**

1. In the **CAM** scene, right-click the camera source → **Filters**
2. **+** → **Image Mask/Blend**
3. Type: **Alpha Mask (Alpha Channel)** · Path: `corner-mask.png` (this folder)
4. Close, then point the `frame.html` source at
   `…/frame.html?bezel=0` (untick *Local file* to use a URL) and refresh its cache

The camera is now genuinely rounded, the corners are transparent, and whatever is
behind the scene shows through them. The mask matches the frame exactly (26 px
inset, 44 px radius) — if you change `radius` or `margin`, edit the same values in
`mask.html` and regenerate the PNG with the command written at the top of the file.

Apply the filter to the camera source *inside* the CAM scene (it then follows the
scene everywhere it is nested), or to the nested CAM scene item itself if you would
rather round the whole composite in one go.

**The quick fix:** just `frame.html?bezel=0`. No black anywhere, but the video keeps
its square corners and the hairline frame simply sits on top of the picture.

---
## Using both at once

The defaults already nest: the HUD keeps clear of the title bar and of the bezel.
Two small tastes to adjust if you want:

- LIVE shows twice (title bar + HUD) → `frame.html?live=0` or `camera.html?live=0`
- Clock shows twice → `frame.html?clock=0` (the HUD one is the big one)
