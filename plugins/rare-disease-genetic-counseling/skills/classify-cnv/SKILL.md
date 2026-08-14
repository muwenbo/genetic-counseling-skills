---
name: classify-cnv
description: Build a reviewable ACMG/ClinGen constitutional CNV classification proposal for a germline deletion or duplication. Use when given a chromosomal interval or CNV and asked to classify a loss/gain, apply the Riggs point metric, interpret section scores, handle hg19 liftover, or add phenotype, inheritance, segregation, reported-case, or case-control evidence.
---

# Classify a CNV

Use the CNV Classification API as a deterministic evidence engine. Preserve its
complete audit trail and label the tier as requiring qualified human review.

## Required inputs

- chromosome;
- 1-based inclusive start and end;
- `loss` or `gain`;
- explicit `hg19` or `hg38` genome build.

Optional clinical evidence must already be reviewed and separated into proband
versus published/reported evidence.

## Workflow

1. Parse the interval and echo chromosome, coordinates, type, genome build, and
   coordinate convention.
2. Compute inclusive size as `end - start + 1` and show it before calling a
   service.
3. Stop if the genome build is absent. Never adopt the API's hg38 default.
4. Map only supplied, reviewed evidence into `hpo_terms`, `inheritance`,
   `phenotype_consistency`, `reported_cases`, `reported_segregation`, and
   `case_control_studies`. Do not send raw narrative or identifiers.
5. Batch variants in one direct REST request to
   `POST https://cnvclassifier.viknox.com/api/v1/classify`.
6. Preserve classification, total points, section scores, every evidence hit,
   suggested ranges, pending evidence, and liftover fields.
7. If liftover fails, keep classification null and report the reason. Do not
   score or reinterpret the original hg19 coordinates as hg38.
8. Present the result as an automated proposal, followed by missing evidence,
   limitations, and review questions.

Read `references/cnv-api.md` for the exact request vocabulary, response fields,
rate limit, and failure semantics.

## Hard stops

- missing or unsupported build;
- invalid chromosome, coordinate order, or CNV type;
- failed/unreliable liftover;
- clinical evidence whose source or meaning cannot be distinguished.

Never coerce a null result to VUS, invent evidence to move a coordinate-only
VUS, or imply that the service is autonomously diagnostic.
