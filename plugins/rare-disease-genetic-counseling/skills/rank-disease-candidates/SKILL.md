---
name: rank-disease-candidates
description: Rank and explain rare-disease candidates from reviewed HPO terms, explicitly absent findings, observed genes, and optionally annotated variants. Use for phenotype-only differential generation, variant-backed gene prioritization, reconciling phenotype and genotype rankings, or investigating why a candidate was or was not retrieved.
---

# Rank disease candidates

Keep phenotype-only retrieval and variant-backed prioritization distinct. A rank
is evidence for review, not a diagnosis.

## Select the mode

- Use `phenotype_only` for reviewed HPO terms without relying on a variant set.
- Use `variant_backed` when annotated variants and assay context are available.
- Use `both` to compare the two lists without collapsing them into one score.

## Workflow

1. Accept only reviewed positive HPO terms and explicitly absent terms. Do not
   convert unmentioned features to negatives.
2. Inspect obsolete/replacement status and graph annotation coverage with
   `GET /hpo/terms/{hp_id}`. Drop or replace graph-dead terms for graph ranking
   while retaining the original proposal in the audit trail.
3. For phenotype-only mode, call the configured knowledge-graph REST API at
   `POST /candidates` with `limit: 50` and `detail: "standard"`. Inspect both
   score-selected and support-selected candidates.
4. For variant-backed mode, accept a user-supplied or separately generated
   prioritization result. Review inheritance, phase, compound heterozygosity,
   phenotype match type, skipped variants, and assay coverage—not only rank.
5. In `both` mode, show agreement, disagreement, and evidence unique to each
   mode. Do not average unlike scores.
6. Explain graph and assay coverage limitations before interpreting a negative
   result.

## Output

For each candidate, report mode, disease identifier/name, associated genes,
inheritance, matched phenotypes and relation quality, explicit contradictions,
variant/inheritance support when applicable, selection reason, and limitations.
End with unresolved alternatives and whether the candidate set is adequate.

Read `references/ranking-guardrails.md` before interpreting graph scores,
support-arm candidates, or absent results.

## Stop conditions

- Stop phenotype-only ranking when there is no reviewed positive phenotype.
- Qualify stale, partial, or failed prioritization output.
- Report unavailable infrastructure separately from an empty candidate list.

Never claim that an associated gene was tested, assign an unnamed variant to a
gene, or treat an unreturned disease as excluded.
