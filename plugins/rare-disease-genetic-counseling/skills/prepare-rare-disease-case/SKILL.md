---
name: prepare-rare-disease-case
description: Structure English or Chinese rare-disease germline clinical narratives into reviewable findings, explicit negatives, suspected diagnoses, treatments, confounders, missing information, and candidate HPO terms. Use when preparing a case, extracting phenotypes, reviewing a referral note, normalizing clinical findings, or assembling phenotype input before disease or variant analysis.
---

# Prepare a rare-disease case

Produce a case-preparation proposal, not a diagnosis. Preserve what the source
actually asserts and make every normalization reviewable.

## Workflow

1. Keep raw clinical text local unless the user explicitly authorizes a suitable
   remote service. Remove direct identifiers from analysis payloads.
2. Extract short findings and assign each an assertion (`present`,
   `explicitly_absent`, `suspected`, or `unknown`) and temporality (`current`,
   `historical`, `resolved`, `recurrent`, or `unknown`).
3. Separate phenotypes, laboratory abnormalities, infections, anatomical
   findings, diagnoses, treatments/exposures, and family history.
4. Preserve a short source span for each proposal. Do not infer a negative from
   silence or turn a differential diagnosis into a finding.
5. Normalize laboratory values only when the value, unit, age-appropriate
   reference range, and sampling context support a named abnormality.
6. Extract short finding phrases locally. Send only the minimized phrases to
   the configured knowledge-graph REST API at `POST /hpo/search`; preserve
   assertion polarity locally because this endpoint maps phrases, not negation.
7. Propose one HPO term per finding. Keep alternates for audit; never add all
   top-k candidates to the case.
8. Call `GET /hpo/terms/{hp_id}` to check obsolete replacements and
   `n_annotated_diseases` before disease ranking.
9. Present the structured findings, HPO proposals, confounders, and missing-data
   questions for human review.

## Output

Return:

- case scope and supplied demographics;
- structured observations with assertion and temporality;
- HPO proposals grouped as accepted, unresolved, or rejected;
- treatments/exposures and interpretation confounders;
- missing information, with what it blocks;
- tool provenance and known extraction limitations.

Use the shared case schema when producing JSON. Read
`references/case-preparation.md` for assertion examples and the minimum review
checklist.

## Stop conditions

- Ask for clarification when negation scope or source meaning cannot be
  preserved.
- Leave numeric laboratory interpretation unresolved when age, unit, reference
  range, or treatment timing is missing.
- Report a capability gap when phenotype services are unavailable. Do not
  fabricate HPO mappings.

Never diagnose the proband, treat unmentioned findings as absent, or promote a
suspected disorder or infection to confirmed.
