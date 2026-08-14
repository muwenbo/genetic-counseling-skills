# Assay blind spots and orthogonal tests

This matrix is a hypothesis guide, not a claim that every assay has the listed
limitation. Confirm the laboratory's platform, pipeline, coverage, and validated
reportable range.

| Possible mechanism | Common blind spot | Orthogonal test examples |
|---|---|---|
| Exon/gene or larger CNV | sequence-only panel or WES with weak CNV calling | exon-level del/dup assay, MLPA, CMA/SNP array, validated CNV analysis |
| Balanced rearrangement | short-read sequence and dosage assays | karyotype, targeted FISH, genome sequencing with SV analysis |
| Repeat expansion | standard short-read variant calling | repeat-primed PCR, sizing assay, Southern blot or validated long-read assay |
| Imprinting/methylation defect | sequence analysis | methylation-specific testing, MS-MLPA, disorder-specific assay |
| UPD | singleton sequence analysis without parental/haplotype analysis | SNP array or trio-based UPD testing; methylation testing when relevant |
| Deep-intronic/regulatory variant | WES or narrow panel | genome sequencing, RNA studies, targeted assays guided by a candidate gene |
| Splicing effect not resolved in silico | DNA-only analysis | clinically appropriate RNA assay using informative tissue |
| mtDNA variant/heteroplasmy | nuclear-focused assay or unsuitable tissue | mtDNA sequencing with heteroplasmy assessment in appropriate tissue |
| Low-level mosaicism | insufficient depth or tissue mismatch | high-depth targeted testing and/or an informative alternate tissue |
| Complex structural variant | short-read small-variant pipeline | genome/SV analysis, long-read sequencing, cytogenetic test as appropriate |

## Selection rules

1. Verify QC before invoking an assay blind spot.
2. Require a phenotype combination specific enough to justify a targeted
   mechanism hypothesis.
3. Explain why the completed assay could have missed that mechanism.
4. Prefer a test that directly observes the proposed mechanism.
5. Rank tests by diagnostic coverage, burden, feasibility, and whether one test
   addresses multiple credible hypotheses.
6. Cap output at three hypotheses.

Use “consistent with,” “raises the possibility,” and “requires orthogonal
confirmation.” Do not say the proband has the hypothesized disorder.
