---
name: review-variant-table
description: Inspect and normalize testing-company Excel, CSV, or TSV germline variant exports into a reviewable variant inventory. Use when a user uploads a laboratory variant table and wants to identify the data sheet or header, map Chinese or English columns, audit company annotations, verify table structure, shortlist variants, or prepare selected records for disease ranking or sequence/CNV classification.
---

# Review a variant table

Treat the workbook as an untrusted laboratory export. Preserve its assertions and
lineage while producing an evidence-backed, reviewable scientific mapping. Do not treat a
company classification, filter, or candidate list as independently verified.

## Required inputs

- local `.xlsx`, `.csv`, or `.tsv` file;
- assay and sample scope when known;
- explicit genome build before genomic normalization or classification;
- a resolved sheet, header, and column mapping, established from local evidence
  or clarified with the user only when uncertain.

Legacy `.xls`, password-protected files, and unsupported structural-variant
representations require a qualified conversion or a different workflow.

## Workflow

1. Keep the file local. Do not upload workbook contents or previews to a separate
   model or scientific API. Do not print filenames, patient identifiers, or raw
   rows in logs or chat.
2. Run the bundled inspector without altering the source:

   ```bash
   python3 scripts/review_variant_table.py inspect INPUT.xlsx --output inspection.json
   ```

3. Review the workbook inventory, candidate header rows, hidden sheets, formulas,
   dimensions, and possible identifier columns. The script proposes candidates;
   it never silently selects one.
4. Establish assay, sample, genome-build, coordinate, and variant-type scope.
   Distinguish called variants from filtered or report-selected variants.
5. Propose a source-column mapping. Preserve the original header and cell value,
   and label laboratory classifications, ACMG codes, frequencies, and database
   assertions as `*_supplied`.
6. Proceed with extraction and shortlisting when sample attribution, table
   mapping, and required genome-build context are clear from the conversation
   and local file evidence. Record the basis; do not require a separate
   confirmation turn or ask again about resolved facts. Ask only about material
   uncertainty that remains after inspection, naming the source headers (for
   example, `Gene`, `HGVS`, `Index_Zygosity`), not column letters or numbers.
   Read the reference's clarification rules for missing or conflicting context.
7. Once the needed context is resolved, create a mapping JSON using source
   header names where unique and run deterministic extraction:

   ```bash
   python3 scripts/review_variant_table.py extract INPUT.xlsx \
     --sheet-index 2 --header-row 3 --data-start-row 4 \
     --mapping mapping.json --genome-build hg38 \
     --coordinate-convention 1-based --sample-scope proband_only \
     --output extracted.json
   ```

8. Reconcile examined, accepted, unresolved, rejected, and blank row counts. Review every
   row-level issue, mixed sample/build signal, duplicate representation, and
   incomplete allele before shortlisting.
9. Before phenotype-based prioritization, run an evidence-preserving safety
   recall across every reviewed record. Retain separate lanes for supplied
   pathogenic/likely pathogenic assertions, supplied database pathogenic/likely
   pathogenic assertions, predicted loss-of-function or canonical splice
   consequences, inheritance-relevant zygosity or repeated-gene observations,
   and phenotype-linked records. Take the union of the lanes; never use a
   phenotype-derived gene list or top-k disease result as an inclusion filter.
   Keep missing population frequency as `unknown` and retain severe-consequence
   records for review rather than treating missing frequency as a failed rarity
   test.
10. Produce a `variant_table_review` artifact using the shared schema. Copy only
   reviewed candidate variants into `case_context.variants`; this local handoff
   does not require a separate confirmation when the analysis is authorized.

Read `references/variant-table-guardrails.md` fully before mapping columns,
filtering rows, or interpreting company-supplied annotations. The script accepts
only scientific fields listed in that reference and never copies identifier
columns into its extraction output.

## Downstream routing

- Send reviewed phenotype plus an imported prioritization result to
  `rank-disease-candidates`; keep its score separate from the laboratory rank.
- Send one reviewed sequence variant and one disease/inheritance context to
  `classify-sequence-variant`.
- Route reviewed deletions or duplications with explicit build and 1-based
  inclusive coordinates to `classify-cnv`.
- Use `find-variant-literature` for claims that require publication evidence.

## Hard stops

- selected sheet, header, data range, or sample scope is unresolved;
- genomic build or coordinate convention is missing where required;
- REF/ALT, transcript, or allele representation is ambiguous;
- multiple samples or builds are mixed without a reliable discriminator;
- low-confidence parsing, malformed output, or row-count mismatch;
- the requested file contains direct identifiers that cannot be excluded from
  the working artifact;
- a service or parser failure is being mistaken for an empty table.

Never delete rows silently, overwrite the source workbook, equate a laboratory
filter with benignity, infer that an unlisted gene was adequately tested, or
classify a table wholesale without variant-level review. Never let graph rank,
phenotype rank, a top-k cutoff, a blank supplied classification, or missing
frequency prevent a record from entering the applicable safety-recall lane.
