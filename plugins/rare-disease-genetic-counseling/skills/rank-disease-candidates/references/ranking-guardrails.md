# Candidate-ranking guardrails

## Phenotype-only graph retrieval

- Supply at least one reviewed positive HPO term.
- Use negative HPO terms only for explicit absences.
- Use one primary HPO mapping per source finding.
- For Chinese or mixed-language source findings, require an agent-verified or
  reviewer-resolved English retrieval phrase in the audit trail. Do not re-query
  raw Chinese text.
- Use `https://rdkg.viknox.com.cn`; record the base URL and `/healthz` version.
- Check `n_annotated_diseases`; a zero means the term cannot contribute to graph
  ranking, not that the finding is invalid.
- Inspect candidates selected through the support arm as well as top scores.
- Read relation quality: exact and patient-more-specific matches generally carry
  stronger clinical meaning than patient-more-general matches.
- Treat contradictions as penalties, not automatic exclusions, because
  expressivity can vary.
- Associated genes are graph context. They are not evidence that a patient was
  tested or carries a variant.

The knowledge graph has incomplete disease-phenotype coverage. “No good candidate
was retrieved” and “the disease was excluded” are never equivalent.

## Two-lane recall and reconciliation

When reviewed variants are available, maintain two independent lanes:

1. phenotype-first retrieval from reviewed HPO terms;
2. variant-first recall from the complete reviewed table or imported
   prioritization result.

Take the union before ranking. Graph rank and phenotype-derived gene lists may
change priority but must not determine eligibility for variant review. Inspect
all records retained by supplied pathogenic assertions, database pathogenic
assertions, severe consequences, inheritance-relevant zygosity, repeated-gene
observations, or other reviewer-approved recall lanes even when their gene or
disease is absent from graph top-k results.

Missing frequency remains unknown. Preserve severe-consequence candidates with
unknown frequency and state that population rarity has not been established.
Likewise, a blank supplied classification is missing evidence, not a reason to
skip another recall lane.

## Variant-backed prioritization

Inspect:

- variant consequence and call quality;
- population frequency and relevant population maximum;
- inheritance fit and proband sex;
- phase and second-hit evidence for recessive disease;
- disease-specific phenotype matches and match types;
- skipped variants and pipeline warnings;
- assay coverage and CNV contribution;
- whether the result is stale after case/HPO/variant changes.

Run an explicit rare loss-of-function sweep when the source system supports it.
Do not let a rank suppress an obvious high-impact, phenotype-relevant candidate.

## Reconciliation output

Show three groups:

1. supported by both phenotype and variant evidence, including variant-first
   candidates whose phenotype support is established during reconciliation;
2. phenotype-supported but lacking a suitable detected variant;
3. variant-supported but absent from graph retrieval, weak in phenotype, or
   contradictory in phenotype.

Do not average graph similarity and genotype likelihood scores. Explain the
evidence dimensions separately.
