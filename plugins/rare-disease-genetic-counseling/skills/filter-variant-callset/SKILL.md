---
name: filter-variant-callset
description: Filter a large, locally stored annotated germline WES/WGS callset (VCF, TSV/CSV, or Excel) into a reviewable variant shortlist using reviewer-approved criteria. Use when filtering a full annotated callset that has no external prioritization result, by frequency, consequence, gene panel, quality, and candidate zygosity. Not for curated laboratory report tables (use review-variant-table), and not as an automatic step within disease ranking.
---

# Filter a variant callset

Produce a candidate shortlist, not a diagnosis. A filter selects variants for
review; it never excludes a gene, proves a variant absent, or confirms an
inheritance pattern. Every threshold is a reviewer decision recorded in the audit
trail.

This is a standalone local filtering utility. `rank-disease-candidates` consumes
a prioritization result and never invokes this skill automatically; keep any
funnel produced here separate from a disease ranking.

## When to use

- Prefer an existing external prioritization (e.g. Exomiser, LIRICAL, a pipeline
  rank) when one exists; a trustworthy external result does not need filtering.
- Use this skill to filter a large annotated **callset** (thousands to millions
  of variants) that has no external prioritization result.
- This skill is for callsets, not curated **laboratory report tables** (tens of
  rows, human shortlist). Route those to `review-variant-table` instead.

## Required inputs

- local annotated `.vcf`/`.vcf.gz`, `.tsv`, `.csv`, or `.xlsx` callset;
- explicit genome build;
- annotations already present in the file (frequency, consequence, gene). This
  skill never adds annotations or contacts the network.

## Workflow

1. Keep the callset local. Do not upload it, previews, or rows to any remote
   model or scientific service. Do not print filenames, sample identifiers, or
   raw genotype-bearing rows.
2. Run the bundled inspector without altering the source:

   ```bash
   python3 scripts/filter_variant_callset.py inspect INPUT.vcf.gz --output inspection.json
   ```

3. Review the reported format, variant count, chromosome coverage, sample
   columns, and **candidate annotation fields**. The script proposes field specs
   (`INFO/…`, `CSQ/…`, `COL/…`); it never selects one. For VCF, the fixed fields
   `QUAL`, `FILTER`, `GT`, and `FORMAT_DP` are always addressable.
4. Establish the build, the frequency field and population it represents, the
   consequence field, and any HPO-derived or panel gene list. Decide the
   inheritance-driven zygosity requirement, if any.
5. Present the chosen field mapping and thresholds for human review. Stop on an
   ambiguous field rather than guessing.
6. After review, write a params JSON and run deterministic filtering:

   ```bash
   python3 scripts/filter_variant_callset.py filter INPUT.vcf.gz \
     --params params.json --output prioritization.json
   ```

7. Reconcile the returned funnel (`examined → after_consequence → after_frequency
   → after_gene → after_quality → after_zygosity → shortlisted`) and the
   excluded-class counts. Confirm the counts before interpreting the shortlist.
8. Report the frequency/consequence/coverage limits of the filter before treating
   an empty or short shortlist as meaningful.

## Params

The filter accepts only these keys: `genome_build` (required), `format`,
`af_field`, `af_max`, `keep_unknown_af` (default true), `consequence_field`,
`consequence_include` or `consequence_max_rank`, `gene_field`, `gene_allowlist`,
`quality_field`/`quality_min`, `depth_field`/`depth_min`, `require_zygosity`
(`hom`/`het`), `zygosity_field`, `chrom_field`/`pos_field`/`ref_field`/`alt_field`
(tables), `sheet_index`/`header_row`, and `limit`. Field values are spec strings
such as `INFO/gnomad_AF`, `CSQ/Consequence`, or `COL/gnomAD_AF`.

## Output

A `variant_prioritization` artifact: shortlisted candidates with supplied
annotations preserved and labeled, the exact parameters used, the stage funnel,
the count of unknown-frequency variants kept, and excluded-class counts. Rank
stays rarer-and-more-severe-first. Copy the shortlist into a prioritization result
for `rank-disease-candidates`; keep its rank separate from any laboratory rank.

Read `references/callset-filtering-guardrails.md` fully before choosing a
frequency field, a consequence set, or an inheritance requirement.

## Hard stops

- genome build is missing;
- the annotation field for a requested filter cannot be resolved unambiguously;
- frequency or consequence filtering is requested on a callset that carries no
  such annotation;
- samples or builds are mixed without a reliable discriminator;
- the funnel count does not reconcile, or the parser output is malformed;
- the file is a curated laboratory report table (route to `review-variant-table`);
- a parser or service failure is being mistaken for an empty callset.

Never treat a variant without a frequency annotation as rare or common by
default, infer phase, segregation, compound heterozygosity, or de-novo status
from the callset, equate a removed variant class with benignity, or treat a gene
absent from the shortlist as adequately assessed.
