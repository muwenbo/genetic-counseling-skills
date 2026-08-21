# Sequence-classification guardrails

## Representation gate

- Require an explicit assembly for genomic coordinates.
- Preserve the original representation.
- Resolve obsolete RefSeq transcript HGVS through an exact contextual and
  canonical genomic allele. Preserve both transcript versions and stop on
  ambiguous mapping; never update a version suffix by string substitution or
  equate variants solely because their c. coordinates match.
- Normalize VCF-style genomic input and independently verify REF on its declared
  GRCh37 or GRCh38 assembly before annotation. Do not liftover solely to call VEP.
- Treat genomic RefSeq HGVS as genomic input requiring an explicit build. If it
  cannot be normalized to one verified VCF-style allele, stop before annotation.
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

List every criterion state, original and effective strength, source, reasoning,
signed point effect, confirmation status, engine agreement/disagreement,
missing evidence, limitations, and required reviewer action. A criterion that
is `not_met`, `not_applicable`, or `not_evaluated` contributes zero points but
remains visible so missing evidence cannot masquerade as negative evidence.

When an applicable VCEP specification defines a point system, use that system
and cite its version. Otherwise label the tally as the **Tavtigian et al. 2020
Bayesian ACMG/AMP point calibration** (PMID 32720330; DOI
`10.1002/humu.24088`) and use:

| Evidence strength | Pathogenic points | Benign points |
|---|---:|---:|
| Supporting | +1 | -1 |
| Moderate | +2 | -2 |
| Strong | +4 | -4 |
| Very strong | +8 | -8 |
| Stand-alone benign | not applicable | -8 |

Interpret the signed total as: Pathogenic at least 10; Likely pathogenic 6-9;
Uncertain significance 0-5; Likely benign -1 through -6; Benign at most -7.
Show pathogenic and benign subtotals and the arithmetic leading to the signed
total. Also apply the applicable rule-based ACMG/AMP combining criteria. Treat
any disagreement between the point calibration, combining rules, and a VCEP
rule as a review issue rather than silently selecting the more severe tier.

Do not count the same observation twice through correlated criteria. In
particular, explain whether splice prediction is consumed by a PVS1 decision
path before adding PP3, and whether functional evidence modifies PVS1 or is
counted independently under PS3.

Return the proposal for review; do not submit it to an external clinical system.
