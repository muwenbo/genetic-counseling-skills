---
name: interpret-negative-or-vus
description: Interpret a completed negative or VUS rare-disease germline analysis by checking QC and assay blind spots, generating restrained phenotype-specific hypotheses, and prioritizing orthogonal confirmatory tests. Use when asked what WES/WGS/panel testing may have missed, why a case is negative, what to test next, or how to follow up an inconclusive result.
---

# Interpret a negative or VUS result

Generate hypotheses and next-test recommendations, never a molecular finding or
a rescued diagnosis.

## Prerequisites

- variant analysis is complete;
- the reviewed result is negative or VUS;
- assay type is known;
- QC and relevant coverage have been reviewed;
- a reviewed phenotype gestalt is available.

## Workflow

1. Distinguish a true analytical negative from failed QC, poor coverage, sample
   problems, or an incomplete variant review. Stop on unresolved QC failure.
2. Define blind spots for the actual assay rather than using a generic WES list.
3. Separate two modes:
   - `phenotype_only`: no useful molecular clue;
   - `partial_clue`: a VUS or monoallelic finding suggests a mechanism the assay
     might have missed.
4. Generate at most three hypotheses supported by a specific combination of
   findings. Retain only disorders whose usual mechanism could plausibly evade
   the assay.
5. Rank by phenotype specificity and mechanism fit, not narrative appeal.
6. Recommend an orthogonal test that directly detects each proposed mechanism.
   Prefer a lower-burden test that covers several credible hypotheses when
   appropriate.
7. State the chain: phenotype -> possible mechanism -> assay blind spot -> test.

Read `references/assay-blind-spots.md` for the mechanism/test matrix and wording
rules.

## Output

Return QC status, assay limitations, one to three hypotheses, supporting and
conflicting findings, proposed confirmatory tests, and limitations. Label every
hypothesis as requiring confirmation.

If the phenotype is nonspecific, say that no targeted hypothesis is supported
and describe only broad follow-up options justified by the assay and case.

Never mark a hypothesis as a primary finding, manufacture a diagnosis from a
clean negative, or imply that a point-mutation disorder was missed when the
assay adequately covered and analyzed that mechanism.
