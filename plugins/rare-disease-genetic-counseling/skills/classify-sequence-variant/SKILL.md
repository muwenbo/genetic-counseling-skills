---
name: classify-sequence-variant
description: Build a reviewable ACMG/AMP and applicable ClinGen VCEP classification proposal for a constitutional germline sequence variant. Use when given genomic coordinates, HGVS, a gene/protein change, rsID, or an imported variant and asked to classify, interpret pathogenicity, evaluate ACMG criteria, or apply gene-specific VCEP guidance.
---

# Classify a sequence variant

Produce one disease-context-specific proposal. Do not submit a classification or
present an automated tier as a clinical verdict.

## Required inputs

- asserted variant;
- explicit genome build for genomic coordinates;
- disease and inheritance context;
- transcript context or permission to propose one;
- zygosity and available phase/segregation evidence.

Missing contextual evidence may be recorded as unknown, but stop when it changes
normalization, VCEP selection, or criterion applicability.

## Workflow

1. Parse the asserted representation without silently repairing it.
2. If the input is genomic and the build is missing, stop before any tool call.
3. Use the configured normalization REST service when available. Require a
   single GRCh38 candidate and verified REF/ALT. Preserve the original
   representation, endpoint provenance, and all liftover warnings.
4. Establish transcript, gene, disease, inheritance, zygosity, and phase.
5. Retrieve annotations, population frequencies, gene mechanism, ClinVar
   context, and relevant prediction evidence from configured sources.
6. Select a VCEP specification by gene, disease, and inheritance. Read the
   applicable guideline fully and record its version and upstream commit. If
   multiple specifications apply, stop for context rather than choosing by gene
   alone.
7. Evaluate every ACMG criterion as `met`, `not_met`, `not_applicable`, or
   `not_evaluated`. Record effective strength, rationale, and evidence source.
8. Use the configured sequence-evidence REST service as a corroborating engine
   when available. Treat unimplemented criteria as not evaluated and surface
   disagreements.
9. Build a point tally only after criterion strengths are resolved. Present the
   proposal, missing evidence, and review questions.

## Hard stops

- missing genome build for genomic input;
- REF mismatch, unreliable liftover, or unresolved multiple representations;
- missing disease/inheritance context that changes VCEP selection or criteria;
- unsupported mitochondrial, mosaic, complex, or structural representation.

Read `references/classification-guardrails.md` before applying PVS1, population
criteria, case-level evidence, or a VCEP modification.

Never infer de novo status or phase, apply PVS1 from consequence alone, treat
gnomAD absence as proof, or submit a classification without explicit approval.
