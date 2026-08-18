# Pinned variant-classifier integration

## Reused resources

The repository pins `muwenbo/vcep-classification-skills` at commit
`05bf1f6bce4e6be04f9e52b55db1d5fee03029d9`. Reuse only these upstream
operations through `scripts/upstream_variant_adapter.py`:

- `variant-classifier/scripts/vep_annotate.py` for Ensembl VEP annotation;
- `variant-classifier/scripts/check_vcep_spec.py` for registry lookup;
- `data/vcep_registry.json` and the selected `data/vcep-guidelines/*.md` file.

Run the dependency check before using either operation:

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" status
```

If automatic discovery fails, pass the checked-out repository explicitly with
`--upstream-root` or set `RARE_DISEASE_VCEP_ROOT`. Do not fetch a moving branch
or accept a different commit. Dependency absence or mismatch is a capability
failure, not an empty annotation or a negative clinical result.

## Annotation

For an already normalized and independently checked GRCh38 allele:

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" annotate \
  "chr17:7676154:G:C" --genome-build hg38
```

Transcript HGVS and rsIDs may be submitted without `--genome-build`, but the
returned genomic representation is still an annotation proposal that must be
reconciled with the asserted variant. Genomic input always requires an explicit
build. The adapter refuses hg19 genomic input because the upstream script calls
the GRCh38 Ensembl endpoint and performs no liftover.

The adapter discloses only the scientific variant to `rest.ensembl.org`. It
preserves the upstream JSON summary, returned assembly, representation
concordance, endpoint provenance, and exact upstream commit. It always reports
`ref_alt_independently_verified: false`: VEP output is not an independent
reference-allele check.

## VCEP lookup

After resolving the gene:

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" vcep TP53
```

Select a specification by gene, disease, and inheritance. Gene match alone is
not enough. Read the selected guideline file fully before applying any modified
criterion and record its filename, version, source URL, and upstream commit.

## Deliberately excluded upstream behavior

Do not call upstream `scripts/classify_variant.py`. At the pinned commit it can
apply PVS1 from consequence alone, treat missing population frequency as PM2,
collapse unevaluated criteria, and emit a tier without the disease-context and
evidence-state gates required by this plugin. These results would conflict with
`classification-guardrails.md`.

Do not use upstream report recommendations as counseling advice. Assemble the
classification proposal locally, keep every criterion in one of the four review
states, and use any future automated engine only as a separately labeled
corroborating result.

## Distribution status

The upstream README declares MIT, but the pinned repository has no standalone
`LICENSE` file. Developer-preview use is recorded; public redistribution remains
blocked until the license grant and required notice text are explicit. Codex
plugin installation also caches only the plugin directory, so an unavailable
root-level submodule must remain a visible capability failure until packaging is
resolved.
