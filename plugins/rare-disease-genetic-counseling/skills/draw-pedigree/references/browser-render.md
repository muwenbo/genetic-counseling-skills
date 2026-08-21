# Rendering and exporting through a local browser

Use this after preparing the PED or JSON data file. Pedigree Studio is a
self-contained, version-pinned HTML asset, but application browser URL policies
may reject `file://` navigation. Serve the bundled asset over loopback HTTP
instead; do not try to bypass the policy with `file:`, `data:`, `blob:`,
`javascript:`, or an unapproved custom URL scheme.

## Start the local page

1. Resolve the current skill directory at runtime. Do not use a checkout-specific
   absolute path.
2. Start a temporary server bound only to IPv4 loopback and serve only the
   `assets/` directory:

   ```bash
   python3 -m http.server 0 \
     --bind 127.0.0.1 \
     --directory "<skill-directory>/assets"
   ```

   Keep the long-running command session so it can be stopped later. Read the
   assigned port from its startup output. If the export fallback below will need
   a `POST` sink, start that variant of the handler now instead of restarting
   later.
3. Following the current browser controller's own setup instructions, open a new
   tab at `http://127.0.0.1:<port>/pedigree-chart.html`. Do not reuse a user's
   existing tab unless requested. Click through the landing screen if the editor
   is not already visible.

The HTTP server exposes only the bundled application shell. Keep the prepared
PED/JSON outside the served directory; family data must not appear in the URL,
query string, server path, or request log.

## Load and verify the pedigree

The editor's file inputs are hidden and driven by the visible **Open** and
**Import PED** toolbar buttons. Clicking a hidden `input[type=file]` from an
automated controller either does nothing or opens a native picker the controller
cannot see, so never do that:

1. Attach the file using whichever mechanism the controller supports:

   - **Controllers with a file-chooser event** (most automation drivers): start
     waiting for `filechooser` **before** clicking, then click the visible button
     — **Open** for a JSON project, **Import PED** for a PED — and hand the file
     to the chooser. Clicking the hidden input itself opens nothing.
   - **Controllers with a direct file-input upload operation** (Claude in Chrome):
     locate the hidden input by its `accept` attribute — `application/json` for
     the JSON project, `.ped,text/plain` for PED — and set its files through that
     operation. Do not click a file input on these surfaces; a native picker the
     controller cannot see would open.

   Either way the app's change handler fires. Never put the data into a URL
   parameter.
2. Click **Fit** so the whole chart is inside the viewport.
3. Verify against the source data before exporting — read the rendered
   `svg[data-testid="pedigree-svg"]` markup or take a screenshot, and confirm:

   - the individual count matches, and no extra person appeared (each symbol is a
     `g[data-testid^="node-"]`);
   - every supplied label is drawn — note that a JSON individual without an
     explicit `label` renders as an unlabelled symbol, while PED always labels
     with the individual id;
   - parent/child and mating lines match the intended relationships;
   - affected individuals are filled and unaffected ones are not;
   - the proband marker (`data-testid="proband-arrow"`) is on the intended person;
   - deceased individuals carry the diagonal slash;
   - carrier dots, adoption brackets, twin bars, and genotype bands appear only
     where the data asked for them.

   A blank or partially drawn chart is an import failure, not an empty pedigree —
   check the browser console before retrying.

## Export

The live SVG is an inline DOM fragment. Its raw `outerHTML` is **not** equivalent
to the app's `Export SVG` output: it can omit the SVG namespace, a standalone
viewBox, a white background, and export-only cleanup. Do not write raw
`svg.outerHTML` to a file.

Two export paths exist. Use the first when it works; use the second when it does
not. Both must produce a standalone SVG.

### Path 1 — the app's own export control (preferred)

Click the visible `Export SVG` button and capture the resulting download through
the browser controller's download handling. Some controllers never surface a
download event for a blob-URL click; if the first click produces no observable
download, do **not** click it again. Switch to path 2 instead. Repeated clicks
only queue more invisible downloads.

`Export PNG` is the same story for a raster deliverable.

### Path 2 — assemble the standalone SVG from page-evaluation output

Do not assume the page-evaluation result is a live DOM node. On several
controlled-page surfaces the returned element is a restricted wrapper without
`cloneNode`, `setAttributeNS`, or `XMLSerializer`, so a serializer written to
clone the node inside the page fails there. Read plain values instead.

First deselect (press `Escape` or click empty canvas) so no selection highlight
is in the markup. Then read the geometry and the markup:

```js
const svg = document.querySelector('svg[data-testid="pedigree-svg"]');
if (!svg) return JSON.stringify({ error: 'NO_SVG' });

const box = svg.getBoundingClientRect();
const vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
const w = Number.parseFloat(svg.getAttribute('width') || '')
  || (vb.length === 4 ? vb[2] : 0) || box.width;
const h = Number.parseFloat(svg.getAttribute('height') || '')
  || (vb.length === 4 ? vb[3] : 0) || box.height;
const viewBox = vb.length === 4 && vb.every(Number.isFinite)
  ? vb.join(' ')
  : `0 0 ${w} ${h}`;

const out = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" `
  + `viewBox="${viewBox}"><rect width="100%" height="100%" fill="white"/>`
  + `${svg.innerHTML}</svg>`;
```

Bail out on `NO_SVG` — that is a render failure, not an empty pedigree — and
re-read if `svg.querySelectorAll('[data-export-exclude]').length` is not `0`,
since something is still selected. Export-only cleanup works by not capturing
those nodes; do not try to strip them from the markup string afterwards.

Getting `out` into a file depends on the controller:

- **Return it and write it locally.** Simplest when the controller passes the
  string through.
- **POST it to the loopback server.** Some controllers refuse to return page
  content, blocking large markup or base64 payloads as suspected exfiltration.
  Serve the asset from a small handler that also accepts `POST` and writes the
  body to a local path, then have the page do
  `await fetch('http://127.0.0.1:<port>/save', { method: 'POST', body: out })`.
  The data stays on loopback and never enters a URL, query string, or the
  request line the server logs. Do not stop the server until the file is
  written.

Confirm the saved file's root has the SVG namespace, positive `width` and
`height`, and a `viewBox`, then open or render it once.

### Never

A screenshot of the viewport is a preview only. Do not save it as, or describe it
as, an exported SVG or PNG pedigree.

## Leave the editor available

After verification and export:

1. Mark the agent-created editor tab as a user-facing deliverable using the
   current browser controller's deliverable-tab operation. Do not close it.
2. Stop the loopback server after the self-contained page has loaded. The loaded
   editor remains interactive without the server, while the listener does not
   remain active unnecessarily.
3. Tell the user that they can modify the pedigree in that tab and use its
   `Export SVG`, `Export PNG`, `Export PED`, or `Export JSON` controls. Browser
   edits do not mutate files already delivered by Codex.

If the browser controller cannot preserve a deliverable tab, still return the
verified artifacts and state that the editable page could not be retained.

## Capability fallback

If the selected browser is unavailable, loopback HTTP navigation is rejected, or
the upload/evaluation capability fails twice:

1. stop the temporary server;
2. do not retry with a disallowed URL scheme or silently switch away from a
   browser explicitly selected by the user;
3. return the validated PED/JSON and state that the figure was not generated;
4. identify the failed capability separately from the pedigree data.

There is currently no bundled command-line figure renderer. Do not invent a
rendered result, and do not upload the application or family data to a remote
site as a workaround.
