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

## Workflow

1. Run `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" status`.
   Require the pinned
   upstream commit; treat absence, mismatch, or malformed output as a capability
   failure rather than an empty annotation.
2. Parse the asserted representation without silently repairing it.
3. If the input is genomic and the build is missing, stop before any tool call.
4. Use the configured normalization REST service when available. Require a
   single GRCh38 candidate and verified REF/ALT. Preserve the original
   representation, endpoint provenance, and all liftover warnings.
5. Run the pinned annotation operation through
   `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" annotate`.
   Reconcile its returned
   assembly, coordinates, alleles, and transcript with the verified input. Do not
   treat VEP output as independent REF/ALT verification.
6. Establish transcript, gene, disease, inheritance, zygosity, and phase.
7. Retrieve additional population, gene-mechanism, ClinVar, and prediction
   evidence from reviewed sources. Preserve missing fields rather than treating
   them as absence.
8. Run `python3 "$SKILL_DIR/scripts/upstream_variant_adapter.py" vcep <GENE>`.
   Select a VCEP
   specification by gene, disease, and inheritance. Read the
   applicable guideline fully and record its version and upstream commit. If
   multiple specifications apply, stop for context rather than choosing by gene
   alone.
9. Evaluate every ACMG criterion as `met`, `not_met`, `not_applicable`, or
   `not_evaluated`. Record effective strength, rationale, and evidence source.
10. Do not call upstream `classify_variant.py`; its automatic PVS1 and PM2
    behavior conflicts with this skill's guardrails. Use a separately validated
    sequence-evidence service only as a labeled corroborating engine, treating
    unimplemented criteria as not evaluated and surfacing disagreements.
11. Build a point tally only after criterion strengths are resolved. Present the
   proposal, missing evidence, and review questions.

## Hard stops

- missing genome build for genomic input;
- REF mismatch, unreliable liftover, or unresolved multiple representations;
- missing disease/inheritance context that changes VCEP selection or criteria;
- unsupported mitochondrial, mosaic, complex, or structural representation.

Read `references/classification-guardrails.md` before applying PVS1, population
criteria, case-level evidence, or a VCEP modification. Read
`references/upstream-integration.md` before running the pinned annotation or
VCEP operations.

Never infer de novo status or phase, apply PVS1 from consequence alone, treat
gnomAD absence as proof, or submit a classification without explicit approval.
