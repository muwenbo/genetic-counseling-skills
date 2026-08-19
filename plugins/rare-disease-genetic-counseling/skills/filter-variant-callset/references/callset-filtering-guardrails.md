# Callset-filtering guardrails

Read this file fully before choosing a frequency field, a consequence set, an
inheritance requirement, or interpreting a shortlist.

## Purpose and trust boundary

An annotated callset is a source artifact, not an interpretation. A filter is a
review decision that selects variants for closer study. It never proves a variant
absent, excludes a gene, or confirms a mode of inheritance. Preserve four layers:

1. callset facts: variants, genotypes, and their positions in the file;
2. file-supplied annotations: frequencies, consequences, gene assignments,
   ClinVar labels, and quality metrics already written into the file;
3. reviewer-chosen filter parameters and the resulting funnel;
4. downstream interpretation, performed by other skills after review.

A dropped variant class is an auditable count, not a deletion. The script never
rewrites the source and never adds an annotation the file did not contain.

## Annotations come only from the file

This skill performs no annotation and no network access. If the callset lacks a
frequency, consequence, or gene annotation, that filter cannot run — this is a
hard stop, not a reason to substitute a default or an external lookup. Routing a
callset to a separate annotator is a different, explicitly authorized workflow.

## Frequency

- Name the population the frequency field represents. A population maximum
  (popmax/gnomAD popmax) is generally safer for rare-disease filtering than a
  global mean, which can hide a common allele in one population.
- Multiple frequencies in one annotation (e.g. `0.01&0.2`) are reduced to their
  maximum before comparison. Confirm this matches your intent.
- **Missing frequency is unknown, never rare or common.** With
  `keep_unknown_af: true` (the default) an unannotated variant survives the
  frequency stage and is counted in `unknown_frequency_kept`; it is never silently
  treated as passing a rarity threshold. Set `keep_unknown_af: false` only when
  the reviewer has decided, with reason, to require an explicit frequency.

## Consequence

- Choose either an explicit `consequence_include` term set or a
  `consequence_max_rank` severity tier, not both. The bundled severity order is a
  convenience, not a clinical ontology; confirm the file's terms match it.
- A variant whose consequence field is present but empty is excluded by the
  consequence stage. A variant with a multi-term consequence passes if any term
  qualifies.
- A rare loss-of-function sweep (stop_gained, frameshift, splice acceptor/donor)
  is a reasonable first pass, but a restrictive consequence filter can hide a
  phenotype-relevant missense or regulatory variant. State the tradeoff.

## Gene panel

- A gene allowlist (HPO-derived or a clinical panel) narrows the shortlist but can
  discard the causative gene when the phenotype list is incomplete or the disease
  is atypical. A gene absent from the shortlist was not assessed for adequacy;
  it was filtered out.
- Match the allowlist to the gene field's identifier type (symbol vs Ensembl ID).

## Inheritance and zygosity

- `require_zygosity` uses the first sample's genotype (VCF `GT`) or a table
  zygosity field as a **candidate** signal only. Homozygous-alt supports a
  recessive hypothesis; heterozygous supports dominant or one arm of a compound
  heterozygote.
- The script does not and must not infer phase, segregation, compound
  heterozygosity, or de-novo status. Those require parental genotypes and a
  separate, reviewed analysis. Do not read a `hom`/`het` tag as confirmed
  inheritance.
- Trio- and family-based reasoning is out of scope here; carry unresolved
  inheritance questions forward as limitations.

## Quality

- Quality and depth floors reduce false positives but can drop real calls in
  low-coverage regions. A variant missing the quality metric is not dropped by
  that stage; missing quality is unknown, not failing.

## Funnel and reconciliation

The output funnel reports survivors after each stage. Confirm
`examined` equals the callset's variant count from `inspect`, and that the
excluded-class counts plus the shortlist account for the drop at each stage. A
funnel that does not reconcile is a hard stop.

## Privacy

Do not expose filenames, sample names, barcodes, or accessions. Do not send the
callset, previews, or rows to remote models or services. Scientific coordinates,
alleles, gene symbols, and supplied frequencies may leave the file only after
review and payload minimization. The script prints no identifiers and no raw
genotype-bearing rows.

## Downstream routing

- Send the shortlist as a prioritization result to `rank-disease-candidates`
  variant_backed; keep its rank separate from any laboratory rank.
- Send one reviewed sequence variant with disease/inheritance context to
  `classify-sequence-variant`.
- Route reviewed deletions or duplications to `classify-cnv`.
- Use `find-variant-literature` for claims that require publication evidence.

A shortlist is not a diagnosis. A surviving variant is a candidate for review. An
excluded variant class is not benign, and a gene missing from the shortlist is not
evidence that the assay assessed it.
