# Pedigree Studio data formats

Two import paths exist. Choose by what the figure must show.

| Need | Format | Import via |
|------|--------|-----------|
| Family structure + affection only | **PED** | `Import PED` button |
| Also proband, deceased, carrier, adopted, twins, consanguinity, variant genotypes | **JSON project** | `Open` button |

## PED (6-column, whitespace-separated)

Columns, in order: `FamilyID  IndividualID  PaternalID  MaternalID  Sex  Affection`

- Fields are split on any whitespace (tabs or spaces both work). Lines that are
  blank or start with `#` are ignored (the `#` convention is a validator nicety;
  the app just skips lines that don't yield 6 tokens).
- **IndividualID** doubles as the on-chart label. Must be unique and not `0`.
- **PaternalID / MaternalID**: `0` when unknown/founder. An id referenced here
  but never given its own row is auto-created as an unknown-sex individual — so
  founders can be implicit, but giving them explicit rows lets you set their sex
  and affection.
- **Sex**: `1`=male, `2`=female, `0`=unknown.
- **Affection**: `1`=unaffected, `2`=affected, `0`=unknown.

Example — affected proband, unaffected parents, one affected sib:

```
# fam  indiv  father  mother  sex  aff
FAM     father  0       0       1    1
FAM     mother  0       0       2    1
FAM     proband father  mother  1    2
FAM     sib     father  mother  2    2
```

PED carries nothing else. Proband ring, deceased slash, carrier dot, genotype
bands, twins and consanguinity loops are **not** expressible in PED — use JSON.

## JSON project (version 1)

Shape (this is exactly what `Export JSON` writes and `Open` reads):

```json
{
  "version": 1,
  "pedigree": {
    "individuals": {
      "<id>": {
        "id": "<id>",
        "sex": "male" | "female" | "unknown",
        "affected": "affected" | "unaffected" | "unknown",
        "deceased": false,
        "proband": false,
        "label": "<display text drawn under the symbol; omitted = no text>",
        "notes": "<optional>",
        "adopted": false,
        "carrier": false,
        "genotypes": { "<variantId>": "ref" | "het" | "hom" | "unknown" }
      }
    },
    "variants": [
      { "id": "<variantId>", "label": "BRCA2 c.1234", "shading": { "color": "#3a6ea5" } }
    ],
    "matings": [
      { "id": "<matingId>", "partners": ["<idA>", "<idB>"], "consanguineous": false }
    ],
    "children": [
      { "matingId": "<matingId>", "childId": "<childId>" }
    ]
  }
}
```

### Minimal complete individual

Write every generated individual with all of these keys present, even when the
value is the default. Older builds of the editor read `individual.genotypes`
without normalizing it, so an individual missing `genotypes` imported cleanly and
then failed at render time with a blank page. The bundled build normalizes and
type-checks imports, but explicit fields keep the JSON reviewable and portable
across builds:

```json
{
  "id": "<id>",
  "sex": "male",
  "affected": "unaffected",
  "deceased": false,
  "proband": false,
  "adopted": false,
  "carrier": false,
  "genotypes": {}
}
```

`genotypes: {}` is the important one; `deceased`, `proband`, `adopted`, and
`carrier` should be written as explicit booleans rather than omitted.

Rules and gotchas:

- `individuals` is an **object keyed by id**, not an array. Each value repeats its
  own `id`.
- A parent-child link is a `children` entry pointing at a `matings` entry; there
  is no `father`/`mother` field on the individual. Put the two parents in
  `matings[].partners` (order not meaningful for correctness; the app infers
  father/mother from each partner's `sex`), then add one `children` entry per
  child of that mating.
- Set `proband: true` on exactly one individual (the arrow/ring).
- `label` is what the chart prints under the symbol. Unlike PED, the id is *not*
  drawn — an individual without `label` renders as an unlabelled symbol. Add
  `label` whenever the figure needs visible names or numbering.
- `genotypes` maps a `variantId` (must exist in `variants[]`) to one of
  `ref | het | hom | unknown`. Each variant renders as its own symbol band, so
  define a `variants[]` entry before referencing it.
- `deceased`, `adopted`, `carrier` are booleans; write `false` rather than
  omitting them.
- Use stable, human-readable ids (`"proband"`, `"mother"`, `"m1"`) — the app is
  happy with any unique strings, and readable ids make the JSON reviewable. (The
  app itself mints UUIDs, but you don't have to.)

Minimal complete project: unaffected parents, affected male proband, unaffected
sister, affected deceased brother. Every individual carries the full key set.

```json
{
  "version": 1,
  "pedigree": {
    "individuals": {
      "father":  { "id": "father",  "sex": "male",   "affected": "unaffected", "deceased": false, "proband": false, "adopted": false, "carrier": false, "genotypes": {} },
      "mother":  { "id": "mother",  "sex": "female", "affected": "unaffected", "deceased": false, "proband": false, "adopted": false, "carrier": false, "genotypes": {} },
      "proband": { "id": "proband", "sex": "male",   "affected": "affected",   "deceased": false, "proband": true,  "adopted": false, "carrier": false, "genotypes": {} },
      "sister":  { "id": "sister",  "sex": "female", "affected": "unaffected", "deceased": false, "proband": false, "adopted": false, "carrier": false, "genotypes": {} },
      "brother": { "id": "brother", "sex": "male",   "affected": "affected",   "deceased": true,  "proband": false, "adopted": false, "carrier": false, "genotypes": {} }
    },
    "variants": [],
    "matings": [ { "id": "m1", "partners": ["father", "mother"], "consanguineous": false } ],
    "children": [
      { "matingId": "m1", "childId": "proband" },
      { "matingId": "m1", "childId": "sister" },
      { "matingId": "m1", "childId": "brother" }
    ]
  }
}
```

To add genotype bands, define the variant and reference its id from each
individual's `genotypes` instead of leaving the map empty:

```json
"variants": [ { "id": "v1", "label": "GENE c.123A>G", "shading": { "color": "#b23a48" } } ]
```

with, for example, `"genotypes": { "v1": "het" }` on a carrier parent and
`"genotypes": { "v1": "hom" }` on the affected proband.
