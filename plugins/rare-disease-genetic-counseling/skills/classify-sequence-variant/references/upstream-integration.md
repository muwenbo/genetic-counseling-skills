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

For a VCF-style genomic allele (the adapter independently checks REF against the
declared assembly before VEP):

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" annotate \
  "chr17:7676154:G:C" --genome-build hg38
```

Transcript HGVS and rsIDs may be submitted without `--genome-build`, but the
returned genomic representation is still an annotation proposal that must be
reconciled with the asserted variant. Genomic input always requires an explicit
build, including genomic RefSeq HGVS (`NC_...:g.`). Normalize genomic HGVS to a
verified VCF-style allele before calling the adapter. The adapter routes `hg38`
to `https://rest.ensembl.org` and `hg19` to
`https://grch37.rest.ensembl.org`. The GRCh37 bridge reuses the pinned upstream
VEP client and response parser without modifying vendored code. It preserves
GRCh37 output and performs no implicit liftover.

## Sequence-allele liftover

The adapter exposes `liftover` for one simple VCF-style SNV/indel:

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" liftover \
  "chr4-1808989-A-T" --from-build hg19 --to-build hg38
```

It calls the assembly-specific Ensembl `sequence/region` and
`map/human/{from_assembly}/{region}/{to_assembly}` operations. It verifies and
normalizes the source allele, requires one contiguous length-preserving mapping,
reverse-complements alleles for a negative-strand mapping, verifies and
normalizes target REF/ALT, and maps the target interval back to the source.

Accept only `status: liftover_ready` with both REF checks and
`roundtrip_concordant: true`. Zero, multiple, split, reference-discordant, or
non-round-tripping mappings stop. Symbolic, breakend, MNV, complex delins,
multi-allelic, ambiguous-base, mitochondrial, and structural variants are
unsupported.

If Ensembl explicitly rejects a versioned RefSeq transcript HGVS as unresolved,
the adapter submits only that scientific HGVS to NCBI Variation and follows
these real operations:

1. `GET /variation/v0/hgvs/{hgvs}/contextuals` for one valid transcript SPDI;
2. `GET /variation/v0/spdi/{spdi}/canonical_representative` for the canonical
   genomic SPDI;
3. `GET /variation/v0/spdi/{canonical_spdi}/hgvs` for genomic HGVS;
4. upstream `vep_annotate.py` on that genomic HGVS.

The output preserves the asserted HGVS, transcript and genomic SPDIs, genomic
HGVS, endpoints, retrieval time, and the annotation input. A current transcript
reported by VEP is equivalent only through the same genomic allele. Mapping
failure, multiple contextual alleles, a non-genomic canonical result, or allele
disagreement is a service failure or hard stop, never permission to edit the
accession version manually. Ensembl timeouts, malformed output, rate limits, and
execution failures do not trigger NCBI fallback.

The adapter discloses only the scientific variant to the assembly-specific
Ensembl REST endpoint and,
when transcript-version resolution is required, `api.ncbi.nlm.nih.gov`. It
preserves the complete upstream JSON summary, returned assembly, representation
concordance, endpoint provenance, and exact upstream commit. It reports whether
a VCF-style REF was independently verified before VEP. Classification-shaped
fields are retained for raw-response fidelity but quarantined from
interpretation, and `classification_ready` remains false.

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

The pinned commit includes a standalone MIT `LICENSE`. Codex plugin installation
still caches only the plugin directory, so an unavailable root-level submodule
must remain a visible capability failure until packaging is resolved or the
dependency is distributed through a reviewed, license-compliant mechanism.
