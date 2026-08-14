# Sequence-classification guardrails

## Representation gate

- Require an explicit assembly for genomic coordinates.
- Preserve the original representation.
- Normalize to one verified GRCh38 allele before annotation.
- Verify REF against the target reference after liftover.
- Treat multiple protein-to-DNA candidates as ambiguous until observed sequence
  data disambiguate them.

## Context gate

Classify one variant for one gene-disease-inheritance context at a time. Record
transcript, zygosity, phase, proband/family evidence, and applicable specification.
Do not choose among multiple VCEP specifications by gene symbol alone.

## Criterion states

Use four states:

- `met`: sufficient applicable evidence supports the criterion;
- `not_met`: evaluated and threshold/requirements were not satisfied;
- `not_applicable`: criterion does not apply to this variant/context;
- `not_evaluated`: required evidence or capability was unavailable.

An automated classifier that does not implement a criterion yields
`not_evaluated`, not `not_met`.

## High-risk criteria

- **PVS1:** require a disease mechanism compatible with loss of function and an
  appropriate transcript/NMD or splice decision path. Consequence alone is
  insufficient.
- **PS2/PM6:** do not infer de novo status. Distinguish confirmed from assumed
  parentage.
- **PS3/BS3:** require an assay applicable to the disease mechanism and interpret
  validation, controls, and direction.
- **PM3/BP2:** require applicable recessive/dominant context and documented phase.
- **PM2/BA1/BS1/BS2:** use the population metric, comparator, ancestry, and
  disease/inheritance threshold required by the applicable specification.
- **PP3/BP4:** avoid double-counting multiple predictors measuring the same
  underlying signal; apply specification-specific thresholds.
- **PP4:** require a phenotype sufficiently specific to the gene-disease pair;
  general organ-system resemblance is insufficient.
- **PP5/BP6:** preserve for source comparison if returned, but follow current
  laboratory/ClinGen policy on whether it contributes to scoring.

## VCEP and provenance

Record VCEP name, gene(s), disease, inheritance, version, source URL, guideline
filename, and exact Git submodule commit. When a guideline and source document
conflict, stop and report the discrepancy.

## Proposal output

List every criterion state, effective strength, source, reasoning, point effect,
engine agreement/disagreement, missing evidence, limitations, and required
reviewer action. Return the proposal for review; do not submit it to an external
clinical system.
