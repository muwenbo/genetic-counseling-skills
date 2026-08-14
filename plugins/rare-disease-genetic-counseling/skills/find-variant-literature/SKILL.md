---
name: find-variant-literature
description: Discover, retrieve, and extract claim-level literature evidence for a rare-disease germline variant, gene-disease pair, ACMG criterion, or CNV region. Use when asked to find papers, search PubMed, fetch known PMIDs, review functional or segregation evidence, count reported cases, investigate de novo/phase evidence, or support a variant interpretation with literature.
---

# Find variant literature

Separate discovery, retrieval, evidence extraction, and classification
interpretation. A relevant paper is not automatically criterion-level evidence.

## Workflow

1. Resolve ambiguous variant nomenclature and disease context before searching.
2. State the evidence question: functional effect, segregation, de novo cases,
   PM3/phase, phenotype specificity, prevalence/case-control, or benign evidence.
3. When PMIDs are not known, use the configured literature discovery source and
   retain the complete, reproducible query and date filters.
4. Deduplicate by PMID, DOI, and article identity. Distinguish primary reports,
   functional studies, reviews, database records, and preprints.
5. Preview metadata before full-text retrieval. Ask before fetching a large or
   nonessential set.
6. Use the upstream paper-finder workflow for selected PMIDs. Retrieve full text
   only when lawfully available; otherwise use citation and abstract metadata.
7. Extract claim-level evidence with allele identity, disease, population,
   assay, family structure, phase/parentage, case counts, phenotype, result, and
   limitations.
8. State whether each claim is directly applicable, indirectly supportive, or
   not usable for the evidence question.

## Output

Return the search strategy, citation inventory, access status, selected claims,
evidence applicability, unresolved questions, and complete PMID/DOI references.
Keep quoted text short and attach a precise source location when available.

Read `references/literature-evidence.md` before converting a paper observation
into ACMG/ClinGen evidence.

## Stop conditions

- Ask for clarification when multiple alleles, transcripts, diseases, or
  inheritance contexts could match the query.
- State that evidence could not be verified when only a citation or inaccessible
  abstract is available.
- Do not infer absent case details from a paper that does not report them.

Never invent full-text findings, use a review as primary case evidence, or
redistribute copyrighted full text beyond its permitted access.
