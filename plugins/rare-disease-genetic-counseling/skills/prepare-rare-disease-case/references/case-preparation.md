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

1. Keep source span and negation output.
2. Confirm candidate meaning, especially when score is below an exact lexical
   match.
3. Accept one term per finding.
4. Check obsolete/replacement state.
5. Check whether a term has disease annotations before graph ranking. A
   graph-dead term can be retained clinically but should be dropped or replaced
   for that retrieval call.
6. Never treat a term extraction miss as a negative phenotype.

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
