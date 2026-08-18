---
name: prepare-rare-disease-case
description: Structure English or Chinese rare-disease germline clinical narratives into reviewable findings, explicit negatives, suspected diagnoses, treatments, confounders, missing information, and candidate HPO terms. Use when preparing a case, extracting phenotypes, reviewing a referral note, normalizing clinical findings, or assembling phenotype input before disease or variant analysis.
---

# Prepare a rare-disease case

Produce a case-preparation proposal, not a diagnosis. Preserve what the source
actually asserts and make every normalization reviewable.

Use the public knowledge-graph base URL `https://rdkg.viknox.com.cn`.

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
6. Determine the source language of each minimized finding. For Chinese or
   mixed-language findings, translate locally into a concise English retrieval
   phrase without adding or removing specificity. Preserve assertion, certainty,
   and temporality outside the phrase.
7. Check the English phrase against the original finding and local context. Mark
   it `agent_verified` and proceed when the meaning and specificity are clear.
   Mark it `review_required` and ask for clarification only when plausible
   alternatives could materially change the HPO mapping. Do not send raw Chinese
   text or negation wording.
8. Call `GET https://rdkg.viknox.com.cn/healthz` without case data and record
   returned versions and graph availability. Then send only agent-verified or
   reviewer-resolved English phrases to the SapBERT vector-search endpoint
   `POST https://rdkg.viknox.com.cn/hpo/search`.
9. Propose one HPO term per finding. Keep alternates for audit; never add all
   top-k candidates to the case.
10. Call `GET /hpo/terms/{hp_id}` to check obsolete replacements and
   `n_annotated_diseases` before disease ranking.
11. Present the structured findings, translation dispositions, HPO proposals,
    confounders, and missing-data questions for human review.

## Output

Return:

- case scope and supplied demographics;
- structured observations with assertion and temporality;
- source language, semantically checked English retrieval phrase, verification
  disposition, and disclosure status for each searched finding;
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
- Stop before `/hpo/search` when the agent cannot resolve an ambiguous, broader,
  narrower, or otherwise meaning-changing English phrase from local context.
- Leave numeric laboratory interpretation unresolved when age, unit, reference
  range, or treatment timing is missing.
- Report a capability gap when phenotype services are unavailable. Do not
  fabricate HPO mappings.

Never diagnose the proband, treat unmentioned findings as absent, or promote a
suspected disorder or infection to confirmed. Never send Chinese clinical text
directly to public graph retrieval.
