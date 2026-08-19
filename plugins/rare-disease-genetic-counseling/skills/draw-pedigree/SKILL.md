---
name: draw-pedigree
description: Create a reviewable clinical pedigree figure or PED/JSON file from user-supplied family-history facts. Use when asked to draw, chart, or diagram a pedigree or family tree; visualize inheritance or segregation across relatives; render affection status, carriers, deceased individuals, proband, twins, consanguinity, or variant genotypes; or convert a PED/family history into a figure—without inferring missing relationships, phenotypes, or genotypes.
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
   genotypes `ref`/`het`/`hom`/`unknown`).
3. For PED, validate before loading:
   `python3 scripts/validate_ped.py <file>.ped` — fix every `ERROR`; `WARN`
   lines about auto-created parents are usually fine.
4. Load and render in the browser following
   [references/browser-render.md](references/browser-render.md): open the bundled
   `assets/pedigree-studio.html`, attach the file to the matching hidden input
   (`.ped` vs `application/json`), confirm it drew, then export.
5. Export the figure — prefer extracting the live `<svg>` via JavaScript (exact,
   no download issues); use `Export PNG` or a screenshot for a raster preview.
   Hand the user the file(s) and a short note of any `unknown` fields.

## Notes

- The tool is fully offline and bundled at `assets/pedigree-studio.html`
  (Pedigree Studio, github.com/muwenbo/pedigree-studio). No install or network.
- If the user only wants the data file (they'll open the tool themselves), stop
  after step 3 and hand over the validated PED/JSON — skip the browser.
- Round-trips: `Export PED`/`Export JSON` re-serialize the current chart, so you
  can ingest an existing pedigree.json, edit it, and reload.
