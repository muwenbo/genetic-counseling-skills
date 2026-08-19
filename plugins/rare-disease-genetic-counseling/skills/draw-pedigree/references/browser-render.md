# Rendering & exporting via the browser (claude-in-chrome)

Use this to load prepared data into Pedigree Studio and get a figure out. The
app is a self-contained offline HTML file; open the **bundled copy** so behavior
is version-pinned:

```
file:///Users/tiger/Developer/rare-skill-dev/plugins/rare-disease-genetic-counseling/skills/draw-pedigree/assets/pedigree-studio.html
```

(When the skill runs from another checkout, resolve the absolute path to
`assets/pedigree-studio.html` inside this skill directory.)

## Load the claude-in-chrome tools first

If deferred, load in ONE ToolSearch call:

```
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__read_page
```

## Steps

1. `tabs_context_mcp` to see current tabs, then `tabs_create_mcp` a NEW tab
   (never reuse the user's tabs unless they ask). `navigate` it to the
   `file://` URL above. Landing page shows a "Try the editor" / launch control —
   click through to the editor if the canvas isn't already showing.
2. Write your prepared `pedigree.ped` or `pedigree.json` to a real file (the
   scratchpad directory is fine).
3. Attach it to the correct **hidden** file input via `file_upload`:
   - PED  → the input with `accept=".ped,text/plain"`.
   - JSON → the input with `accept="application/json"`.
   The inputs are hidden; `file_upload` sets `input.files` directly, which fires
   the app's `onChange` and loads the pedigree without clicking the button. If
   the tool needs a selector, target by the `accept` attribute, e.g.
   `input[accept=".ped,text/plain"]` or `input[accept="application/json"]`.
4. Confirm it rendered: `computer` screenshot, or `read_page`. Expect symbols
   (squares = male, circles = female) with the affected ones filled.

## Getting the figure out

Preferred — extract the live SVG directly (robust, no download sandboxing):

```js
// javascript_tool
const svg = document.querySelector('svg');
return svg ? svg.outerHTML : 'NO_SVG';
```

Write the returned string to `pedigree.svg`. This is byte-for-byte the same
markup the `Export SVG` button would save.

Alternative — click the visible buttons:
- `Export SVG` → downloads `pedigree.svg`
- `Export PNG` → downloads `pedigree.png` (white background, SVG rasterized)
- `Export PED` / `Export JSON` → round-trip the data back out

Downloads land in the browser's default download folder; capturing that path is
less reliable than extracting the SVG via JavaScript, so prefer the JS route
when you need the file programmatically. For a raster preview to show the user,
a `computer` screenshot of the canvas is simplest.

## Guardrails

- Do NOT trigger `alert`/`confirm` dialogs — they freeze the extension.
- If a tool errors twice, stop and report what you tried rather than looping.
- The file is offline and self-contained: no network calls are expected. If you
  see network errors, you likely opened the wrong path.
