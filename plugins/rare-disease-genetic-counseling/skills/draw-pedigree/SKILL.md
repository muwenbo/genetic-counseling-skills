---
name: draw-pedigree
description: Create a reviewable clinical pedigree figure or validated PED/JSON file from user-supplied family-history facts. Use when asked to draw, chart, or diagram a pedigree or family tree; visualize inheritance or segregation across relatives; render affection status, carriers, deceased individuals, proband, twins, consanguinity, or variant genotypes; or convert a PED/family history into a figure—without inferring missing relationships, phenotypes, or genotypes.
---

# Draw a pedigree

Convert a described family into a Pedigree Studio chart. Do not invent
relationships, affection status, sex, or genotypes that were not stated — mark
them `unknown` (`0`) instead. The figure reflects supplied facts; it is not a
clinical interpretation.

## Pick the data format

- **PED** — family structure + affection only. Simple and fast.
- **JSON project** — needed for proband ring, deceased, carrier, adopted,
  twins, consanguinity, or variant genotype bands.

Full column semantics, encodings, and copy-paste examples are in
[references/data-formats.md](references/data-formats.md). Read it before writing
either file; the JSON structure (individuals as an id-keyed object, parents via
`matings` + `children`) is easy to get wrong from memory.

## Workflow

1. Extract the family: each person's id/label, sex, affection, parents, and any
   proband/deceased/carrier/genotype facts. List unknowns explicitly as unknown.
2. Choose PED or JSON per the rule above and write the file (scratchpad dir is
   fine). Encodings: sex `1`/`2`/`0`, affection `1`=unaffected `2`=affected
   `0`=unknown; JSON uses word forms (`male`/`female`, `affected`/`unaffected`,
   genotypes `ref`/`het`/`hom`/`unknown`). In JSON, give every individual the
   complete key set — explicit `deceased`, `proband`, `adopted`, `carrier`
   booleans and a `genotypes` object (`{}` when there are no variants).
3. For PED, validate before loading:
   `python3 scripts/validate_ped.py <file>.ped` — fix every `ERROR`; `WARN`
   lines about auto-created parents are usually fine.
4. When a figure is requested, read
   [references/browser-render.md](references/browser-render.md). Serve the bundled
   `assets/pedigree-chart.html` through a loopback HTTP URL, then load the file
   through the visible control (**Open** for JSON, **Import PED** for PED) with a
   file-chooser wait already armed, or through the controller's direct
   file-input upload operation — clicking the hidden input yourself does nothing
   useful either way. Click **Fit** and verify individual count, labels,
   relationships, affected states, proband marker, and deceased marker against the
   source data. Do not navigate the browser to a `file://` URL.
5. Export the figure with one of the two paths in the rendering reference: the
   app's own `Export SVG` control when the download is observable, otherwise read
   the rendered markup and dimensions and assemble a standalone SVG outside the
   page. Never save the live element's raw `outerHTML`; it omits document-level
   SVG metadata that the app's own `Export SVG` path adds. Do not click the export
   control repeatedly when no download event is exposed, and never present a
   screenshot as an exported SVG or PNG.
6. Keep the loaded editor tab open as a user-facing deliverable so the user can
   adjust the pedigree directly. Once the self-contained page has loaded and any
   export has been written, stop the temporary loopback server without closing
   the tab.
7. If the browser or loopback URL is unavailable, stop the rendering attempt and
   hand over the validated PED/JSON with an explicit note that no figure was
   generated. Do not describe a rendering failure as a successful or empty
   pedigree.

## Notes

- The version-pinned tool is bundled at `assets/pedigree-chart.html` (Pedigree
  Studio, github.com/muwenbo/pedigree-studio), fetched from
  https://pedigree.viknox.com/ and reproduced from upstream commit
  `11321af4821801a4e41bc228c00416c2e40ea302` — sha256
  `820acb0d9ff46268e17e4aba47e1dc4e750e90f58046d26225bbe5e49113871b`.
  License and dependency notices are in `assets/THIRD_PARTY_NOTICES.md`. This build
  validates and normalizes imported JSON; earlier builds crashed to a blank chart
  on an individual with no `genotypes`. Loopback HTTP uses the local network
  stack but does not disclose the family data to a remote service.
- If the user only wants the data file (they'll open the tool themselves), stop
  after step 3 and hand over the validated PED/JSON — skip the browser.
- This skill currently has no bundled command-line figure renderer. Do not claim
  that a fallback SVG or PNG was generated when only PED/JSON is available.
- Round-trips: `Export PED`/`Export JSON` re-serialize the current chart, so you
  can ingest an existing pedigree.json, edit it, and reload.
- Edits made in the retained browser tab do not rewrite previously delivered
  files automatically; the user can use the page's export controls to save the
  revised SVG, PNG, PED, or JSON.
