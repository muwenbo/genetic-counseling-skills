---
name: classify-sequence-variant
description: Build a reviewable ACMG/AMP and applicable ClinGen VCEP classification proposal for a constitutional germline sequence variant. Use when given genomic coordinates, HGVS, a gene/protein change, rsID, or an imported variant and asked to classify, interpret pathogenicity, evaluate ACMG criteria, or apply gene-specific VCEP guidance.
---

# Classify a sequence variant

Produce one disease-context-specific proposal. Do not submit a classification or
present an automated tier as a clinical verdict.

Resolve `scripts/` and `references/` relative to the directory containing this
`SKILL.md`; do not assume the user's working directory is the skill directory.

## Required inputs

- asserted variant;
- explicit genome build for genomic coordinates;
- disease and inheritance context;
- transcript context or permission to propose one;
- zygosity and available phase/segregation evidence.

Missing contextual evidence may be recorded as unknown, but stop when it changes
normalization, VCEP selection, or criterion applicability.

## Coordinate conversion

For a standalone hg19/GRCh37 ↔ hg38/GRCh38 conversion, disease context is not
required. Run:

```bash
python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" liftover \
  "chr4-1808989-A-T" --from-build hg19 --to-build hg38
```

Use this only for simple VCF-style SNV/indel alleles. The adapter normalizes and
verifies source REF, requires exactly one contiguous Ensembl assembly mapping,
handles reverse-strand alleles, normalizes and verifies target REF, and requires
a concordant reverse coordinate mapping. Preserve both alleles and the mapping
audit trail. Stop on REF mismatch, zero/multiple/split mappings, target reference
disagreement, or failed round trip. Do not treat successful liftover as
pathogenicity evidence.

## Workflow

1. Run `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" status`.
   Require the pinned upstream commit; treat absence, mismatch, or malformed
   output as a capability failure rather than an empty annotation. On a clean
   installation, if status reports `approved_setup_available`, explain that setup
   downloads the public MIT-licensed repository at the recorded commit from
   GitHub into a local non-clinical cache. Obtain explicit approval before running
   `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" prepare
   --allow-network-install`, then rerun `status`. The setup request discloses only
   repository and commit metadata—never a variant, case fact, or identifier. If
   approval is declined or setup fails, stop with capability unavailable.
2. Parse the asserted representation without silently repairing it. Genomic
   RefSeq HGVS (`NC_...:g.`) is genomic input and requires a build.
3. If the input is genomic and the build is missing, stop before any tool call.
   Normalize genomic HGVS to one verified VCF-style allele before using the
   bundled annotation adapter; if that normalization capability is unavailable,
   stop rather than treating VEP as the normalizer.
4. For genomic input, route `hg38` to `rest.ensembl.org` and `hg19`/GRCh37 to
   `grch37.rest.ensembl.org`. Keep annotation on the declared assembly; do not
   liftover merely to call VEP. For VCF-style input, the adapter independently
   retrieves the declared-assembly reference sequence and stops on REF mismatch
   before VEP. Preserve endpoint provenance and warnings.
5. For a versioned RefSeq transcript HGVS that Ensembl explicitly rejects as
   unresolved, let the adapter map the asserted HGVS through NCBI Variation
   contextual SPDI to one canonical GRCh38 genomic SPDI/HGVS allele, then
   annotate that allele. Preserve the asserted transcript and every mapping
   representation. Accept a current-transcript annotation only when it resolves
   to that same genomic allele; never infer equivalence from matching c. numbers
   or by replacing the accession version suffix. A timeout, malformed response,
   rate limit, or execution failure remains an Ensembl service failure and must
   not trigger disclosure to NCBI.
6. Run the pinned annotation operation through
   `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" annotate`.
   Preserve its complete returned annotation. Reconcile its returned
   assembly, coordinates, alleles, and transcript with the verified input. Do not
   treat VEP output as independent REF/ALT verification. If the preserved
   response unexpectedly contains classification-shaped fields, quarantine them
   from interpretation and keep `classification_ready: false`.
7. Establish transcript, gene, disease, inheritance, zygosity, and phase.
8. Retrieve additional population, gene-mechanism, ClinVar, and prediction
   evidence from reviewed sources. Preserve missing fields rather than treating
   them as absence.
9. Run `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" vcep <GENE>`.
   Select a VCEP
   specification by gene, disease, and inheritance. Read the
   applicable guideline fully and record its version and upstream commit. If
   multiple specifications apply, stop for context rather than choosing by gene
   alone.
10. Evaluate every ACMG criterion as `met`, `not_met`, `not_applicable`, or
   `not_evaluated`. Record the original and effective strength, rationale,
   evidence source, confirmation status, and signed point effect. Do not omit
   evaluated criteria merely because they contribute zero points.
11. Do not call upstream `classify_variant.py`; its automatic PVS1 and PM2
    behavior conflicts with this skill's guardrails. Use a separately validated
    sequence-evidence service only as a labeled corroborating engine, treating
    unimplemented criteria as not evaluated and surfacing disagreements.
12. Build a point tally only after criterion strengths are resolved. Use the
    applicable VCEP point rules when specified; otherwise label and use the
    Bayesian ACMG/AMP point calibration in
    `references/classification-guardrails.md`. Show pathogenic and benign
    subtotals, the signed total, the tier threshold reached, and the
    corresponding rule-based ACMG/AMP combination. Do not force a tier when the
    point result and applicable combining rules disagree; surface the
    discrepancy for review.
13. Present a criterion table by default, even when the user asks only for the
    final tier. Include criterion, state, effective strength, points, evidence,
    rationale, and limitations or missing confirmation. Follow it with the
    scoring framework/version, arithmetic, threshold interpretation, proposed
    tier, missing evidence that could change the score, and review questions.

## Hard stops

- missing genome build for genomic input;
- genomic HGVS that cannot be normalized to one independently verified
  VCF-style allele;
- REF mismatch, unreliable liftover, or unresolved multiple representations;
- returned VEP assembly differs from the declared genomic build;
- ambiguous transcript-version mapping or disagreement between the mapped
  genomic allele and current-transcript annotation;
- missing disease/inheritance context that changes VCEP selection or criteria;
- unsupported mitochondrial, mosaic, complex, or structural representation.
- liftover of symbolic, breakend, multi-allelic, ambiguous-base, non-contiguous,
  mitochondrial, MNV, or complex delins variants.

Read `references/classification-guardrails.md` before applying PVS1, population
criteria, case-level evidence, or a VCEP modification. Read
`references/upstream-integration.md` before running the pinned annotation or
VCEP operations.

Never infer de novo status or phase, apply PVS1 from consequence alone, treat
gnomAD absence as proof, or submit a classification without explicit approval.
