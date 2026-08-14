# Variant-table review guardrails

Read this file fully before mapping a laboratory export, excluding rows, or
interpreting a supplied annotation.

## Purpose and trust boundary

A testing-company table is a source artifact, not a verified interpretation.
Preserve four distinct layers:

1. workbook facts: sheets, cells, formulas, hidden state, and row locations;
2. laboratory-supplied assertions: filters, classifications, ACMG codes,
   frequencies, phenotype matches, and citations;
3. normalized scientific representations verified independently;
4. model proposals and reviewer decisions.

Do not overwrite one layer with another. A disagreement is an auditable finding,
not permission to silently repair the source.

## Supported inputs

The bundled script reads `.xlsx`, `.csv`, and `.tsv` locally with Python's
standard library. It deliberately rejects legacy binary `.xls`, encrypted or
malformed workbooks, and oversized or suspicious ZIP containers. If a trusted
local conversion is used, retain the original file hash and record the converter,
version, time, and output hash.

Macros are never executed. A macro-enabled or formula-bearing workbook requires
an explicit warning. Formula text and cached values are source assertions; do not
recalculate them and present the result as laboratory output.

## Inspection and review checkpoint

Inventory every sheet, including hidden and very-hidden sheets. Record dimensions,
merged-cell and formula counts, candidate header rows, and possible identifier
columns. Header candidates are heuristic suggestions only.

Before extraction, have the reviewer confirm:

- selected sheet or sheets;
- 1-based header, first data row, and optional last data row;
- whether each row is one allele, genotype, CNV, transcript consequence, or
  report item;
- whether repeated rows represent duplicates or legitimate transcript/sample
  expansions;
- sample roles and whether samples are mixed;
- assay type and scope;
- declared genome build and coordinate convention;
- source-to-canonical column mapping;
- columns that may leave the raw workbook.

Low confidence, malformed parser output, or an ambiguous selection blocks
extraction. Never fall back to the first sheet or row.

## Canonical scientific fields

The extraction script accepts only these fields:

- identity and location: `gene`, `chrom`, `pos`, `start`, `end`, `ref`, `alt`,
  `genomic_hgvs`, `coding_hgvs`, `protein_hgvs`, `rsid`;
- transcript and allele context: `transcript`, `zygosity`, `genotype`,
  `sample_role`, `genome_build`, `cnv_type`;
- call evidence: `depth`, `allele_depth`, `allele_fraction`, `quality`, `filter`;
- annotations: `consequence`, `inheritance_supplied`,
  `classification_supplied`, `acmg_codes_supplied`,
  `population_frequency_supplied`, `clinvar_supplied`.

`sample_role` means a non-identifying role such as `proband`, `mother`, or
`father`; it must not contain a name, medical-record number, laboratory accession,
or sample barcode. Identifier columns are never valid canonical fields.

Common English and Chinese header words can help propose a mapping, but are not
semantic proof. Examples include `基因/Gene`, `染色体/Chromosome`, `位置/Position`,
`参考等位基因/Ref`, `替代等位基因/Alt`, `转录本/Transcript`,
`核苷酸改变/c.HGVS`, `氨基酸改变/p.HGVS`, and `合子状态/Zygosity`.
Confirm meaning against the report legend or laboratory documentation when
available.

## Variant-level validation

For genomic SNVs and indels:

- require an explicit build before normalization;
- verify chromosome, position, REF, and ALT together against that assembly;
- do not treat positional liftover as allele verification;
- distinguish 0-based, 1-based, inclusive, and half-open coordinates;
- preserve multiallelic and left/right-normalization ambiguity;
- do not infer transcript version or repair malformed HGVS silently.

For CNVs:

- establish loss/gain, chromosome, start, end, build, and coordinate convention;
- do not infer CNV type from a gene list alone;
- route supported constitutional losses and gains to `classify-cnv` only after
  review.

For sample and inheritance fields:

- do not infer proband/parent roles from column order or names;
- do not infer de novo status, phase, segregation, or compound heterozygosity;
- treat missing genotype and allele-balance evidence as missing.

## Row disposition and reconciliation

Assign every candidate row one disposition: `accepted`, `unresolved`, or
`rejected`. Rejection requires a recorded reason. Blank rows may be counted
separately but must not conceal nonblank footers or comments.

Reconcile:

`examined rows = accepted + unresolved + rejected + blank rows`

Do not remove variants merely because a laboratory filter says `PASS`, `LowQual`,
`benign`, `not reported`, or an equivalent label. Filtering and shortlisting are
review decisions that preserve the original row and rationale.

Potential duplicate representations should be grouped, not deleted, until the
reviewer determines whether they are duplicate alleles, alternate transcripts,
different samples, or multiallelic decompositions.

## Privacy

Do not expose filenames, names, dates of birth, phone numbers, addresses, medical
record numbers, laboratory accessions, sample barcodes, pedigrees, or free-text
notes. Do not send raw rows or workbook previews to separate remote models or
scientific services. Scientific coordinates, alleles, gene symbols, HPO IDs, and
publication identifiers may leave the workbook only after validation and payload
minimization.

Record disclosed field names and destinations without recording sensitive values.

## Output checklist

The review artifact must contain:

- file hash and format, without the original filename or raw sheet names;
- workbook/sheet inventory and parser warnings;
- reviewed selection and column mappings;
- declared assay, sample, build, and coordinate context;
- row reconciliation;
- accepted records with source sheet/row lineage;
- unresolved and rejected rows with reasons;
- company-supplied annotations labeled as supplied;
- validation issues, missing information, and downstream routing;
- reviewer disposition and provenance.

A candidate shortlist is not a diagnosis. A company classification is not an
independent ACMG/AMP proposal. An absent row or gene is not evidence that the
assay adequately assessed it.
