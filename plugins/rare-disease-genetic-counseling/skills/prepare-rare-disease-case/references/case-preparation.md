# Case preparation reference

## Assertion and temporality

Keep these axes independent.

| Source phrase | Assertion | Temporality |
|---|---|---|
| “has seizures” | present | current or unknown |
| “recurrent pneumonia” | present | recurrent |
| “history of neonatal jaundice” | present | historical |
| “pneumonia resolved after treatment” | present | resolved |
| “no seizures” | explicitly_absent | current or stated period |
| “possible fungal pneumonia” | suspected | current |
| no mention of seizures | no observation | no observation |

Do not encode a suspected diagnosis as a phenotype unless the actual component
finding is independently stated. For example, “possible immunodeficiency” is a
diagnostic concern; low immunoglobulins and recurrent infections are findings.

## Laboratory normalization

Require value, unit, reference interval, age/sex context when relevant, specimen
timing, and major treatment confounders. If these are missing, preserve the
recorded interpretation (for example, “reported low IgG”) without independently
confirming it.

IVIG, transfusion, steroids, antimicrobials, transplantation, and acute illness
may change interpretation. Record them as treatments/exposures and list their
specific confounding effect.

## HPO review

1. Keep source span, source language, assertion, and temporality local.
2. For Chinese or mixed-language input, translate only the minimized finding
   into an English retrieval phrase. Do not translate the whole narrative.
3. Verify semantic equivalence locally. Use `agent_verified` when the mapping is
   unambiguous; use `review_required` only when plausible alternatives could
   materially change the HPO concept. Reviewer-resolved phrases may also be sent.
4. Confirm candidate meaning, especially when score is below an exact lexical
   match.
5. Accept one term per finding.
6. Check obsolete/replacement state.
7. Check whether a term has disease annotations before graph ranking. A
   graph-dead term can be retained clinically but should be dropped or replaced
   for that retrieval call.
8. Never treat a term extraction miss as a negative phenotype.

## Chinese-to-English retrieval phrases

The English phrase is a search key, not a replacement for the source finding.
Keep polarity outside `/hpo/search` because the endpoint maps concepts rather
than negation.

| Chinese source finding | Local metadata | Proposed English search phrase |
|---|---|---|
| `身材矮小` | present | `short stature` |
| `反复肺炎` | present, recurrent | `recurrent pneumonia` |
| `无癫痫发作` | explicitly absent | `seizure` |
| `既往新生儿黄疸` | present, historical | `neonatal jaundice` |

Before sending a phrase, verify that it:

- describes the finding rather than a suspected diagnosis;
- preserves anatomical site, severity, onset, recurrence, and subtype when
  explicitly stated;
- does not invent an observation from a syndrome name or differential;
- contains no name, date, record number, or free-text context;
- is concise English suitable for HPO lexical or semantic search;
- leaves negation, suspicion, and temporality in local structured metadata.

If more than one English phrase could materially change the HPO mapping and
local context does not resolve the choice, keep the alternatives as audit
proposals and stop for reviewer selection. Do not use a model confidence score
alone as evidence of semantic equivalence.

## Minimum review checklist

- age, sex, onset, and course are explicit or unknown;
- infections distinguish organism, site, severity, recurrence, and confirmation;
- congenital anomalies remain separate observations;
- suspected diagnoses remain suspected;
- explicit negatives are source-supported;
- treatment timing is retained;
- family history and consanguinity are requested rather than inferred;
- assay history and genome build are explicit before variant analysis;
- direct identifiers are excluded from analysis payloads.
- every Chinese/mixed finding sent for HPO search has an agent-verified or
  reviewer-resolved English phrase;
- disclosed search phrases and the destination base URL are recorded.
