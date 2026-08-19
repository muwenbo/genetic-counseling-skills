---
name: draft-counseling-summary
description: Draft clinician-facing and optional patient-facing rare-disease germline genetic counseling summaries from reviewed case facts and interpretation proposals. Use when asked to summarize a positive, VUS, or negative result; explain inheritance or family implications; prepare counseling notes; communicate testing limitations; or communicate reviewed follow-up recommendations for professional review.
---

# Draft a counseling summary

Transform reviewed evidence into clear counseling language without changing its
certainty. The result is a draft requiring qualified professional review.

## Required inputs

- reviewed case context and assay scope;
- reviewed result category and molecular interpretation;
- disease/inheritance context at the resolution supported by evidence;
- known family structure;
- approved follow-up recommendations;
- intended audience and language.

Do not draft a definitive result from an unreviewed engine proposal.

## Workflow

1. State the test performed and what result was identified or not identified.
2. Separate molecular result, clinical interpretation, uncertainty, assay
   limitations, family implications, and next steps.
3. For a positive result, explain the reviewed classification and phenotype fit
   without claiming manifestations that were not observed.
4. For a VUS, state that it does not establish or exclude a diagnosis and should
   not independently direct irreversible management or predictive testing.
5. For a negative result, distinguish no causative finding from genetics being
   excluded and state relevant assay limitations.
6. Explain inheritance and recurrence only as far as parental testing,
   penetrance, phase, family structure, and disease mechanism allow.
7. Produce clinician-facing language first. Create patient-facing language only
   when requested, using plain terms without changing the evidentiary meaning.
8. End with unresolved questions, recommendations, and required reviewer status.

Use `assets/counseling-summary-template.md` for the output structure. Read
`references/counseling-language.md` for certainty and family-risk rules.

## Stop conditions

- Stop or qualify when classification review, disease association, inheritance,
  or family relationships are unresolved.
- Do not provide a numeric recurrence risk without the inputs needed to support
  it.
- Return the draft to the user; this public plugin does not write to a clinical
  record system.

Never call a VUS diagnostic, present automated text as a signed report, or give
medical management instructions beyond reviewed recommendations supplied in the
case context.
