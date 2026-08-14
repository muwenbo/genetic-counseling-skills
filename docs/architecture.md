# Developer-preview architecture

## Scope

The first release supports rare-disease constitutional/germline counseling. It
does not cover somatic oncology, pharmacogenomics, reproductive carrier
screening, polygenic risk, or newborn screening as standalone workflows.

The plugin is an orchestration and safety layer. Existing services remain the
source of computed annotations, rankings, and evidence. The plugin owns:

- input validation and normalization gates;
- separation of observed, explicitly absent, suspected, and historical facts;
- tool selection and sequencing;
- provenance and uncertainty preservation;
- human-review checkpoints;
- counseling-oriented output.

It does not own reference databases, primary annotation algorithms, ACMG/ClinGen
scoring implementations, or clinical case storage.

## Planned package

```text
rare-disease-genetic-counseling/
├── .codex-plugin/plugin.json
├── skills/
│   ├── prepare-rare-disease-case/
│   ├── review-variant-table/
│   ├── rank-disease-candidates/
│   ├── classify-sequence-variant/
│   ├── classify-cnv/
│   ├── find-variant-literature/
│   ├── interpret-negative-or-vus/
│   └── draft-counseling-summary/
├── vendor/
│   └── vcep-classification-skills/  # Git submodule
├── scripts/                     # shared REST client helpers, if needed
├── schemas/
└── evals/
```

Skills call the configured scientific REST APIs through small bundled clients.
The public plugin does not depend on Noxia or another clinical record system.
Service-specific request and response contracts remain explicit so API failures
cannot be mistaken for negative clinical results.

## Integration map

| Capability | Source | Integration mode | Plugin responsibility |
|---|---|---|---|
| Finding extraction | skill reasoning, performed locally | in-skill workflow | Preserve spans and negation; require review before accepting HPO terms |
| Laboratory variant-table review | bundled local script plus skill reasoning | local file workflow | Inventory without mutation, exclude identifiers, require reviewed sheet/header/mapping, and preserve company annotations as supplied claims |
| HPO search and phenotype-only disease retrieval | `rd-knowledge-graph` | configurable REST API | Call `/hpo/search`, `/hpo/terms/{hp_id}`, and `/candidates`; check graph coverage and never equate absence with exclusion |
| Optional variant-backed gene ranking | user-supplied prioritization result | imported result | Keep external rank distinct from clinical conclusion; expose inheritance and phenotype evidence |
| Variant normalization | `hgvs-tools` | local HTTP service | Require explicit assembly for genomic input; independently verify REF before classification |
| Sequence evidence engine | `acmg-auto-classifier` | local HTTP service | Label output as automated and incomplete; build a reviewable proposal |
| VCEP guidance | `vcep-classification-skills` | immutable Git submodule | Select disease/inheritance-specific specification and record exact commit/version |
| CNV classification | `cnvclassifier.viknox.com` | remote HTTPS API | Minimize payload, require build, preserve liftover and complete evidence trail |
| Literature | PubMed/PMC via upstream paper finder plus discovery adapter | remote retrieval | Distinguish discovery from PMID fetch; preserve licensing and evidence extraction provenance |
| Pedigree | `pedigree-chart` | future optional export | Generate reviewable PED/JSON; do not infer relatives or genotypes |

## Non-negotiable correctness boundaries

1. **Genome build is required for genomic coordinates.** Never inherit an
   upstream default. A missing build stops normalization and classification.
2. **Coordinates and alleles are verified together.** A successful positional
   liftover does not establish that REF/ALT are correct on the target assembly.
3. **Disease and inheritance context precede classification.** VCEP selection,
   frequency thresholds, PVS1, PM3, PP4, and other criteria can depend on them.
4. **Phenotype assertions retain polarity and certainty.** Unmentioned is not
   absent; suspected is not observed; historical is not necessarily current.
5. **Automated tiers are proposals.** Engine outputs, point totals, and rankings
   are evidence anchors requiring qualified human review.
6. **No silent evidence upgrading.** Missing parental confirmation, phase,
   functional validation, or phenotype specificity must remain missing.
7. **External disclosure is minimized.** Send only the fields required for a
   tool call. Raw narratives, identifiers, dates, and record numbers remain local
   unless the user explicitly authorizes a suitable service.
8. **Writes are isolated.** Analysis never implies authorization to update HPO
   terms, submit a classification, select a report variant, or edit a report.
9. **Laboratory tables are untrusted source artifacts.** Never silently select a
   sheet, drop a row, infer a build, or treat a company filter, classification,
   ACMG code, frequency, or candidate rank as independently verified evidence.

## Provenance envelope

Every tool-derived result should record:

- service or repository name;
- endpoint or repository operation;
- service, artifact, guideline, or Git commit version where available;
- call time;
- declared genome build and coordinate convention;
- request fields sent, with identifiers and narrative excluded or redacted;
- local file hash, pseudonymous sheet reference, source row, reviewed column
  mapping, and row reconciliation for table-derived records;
- warnings, failures, liftover information, and unfilled fields;
- whether a human accepted, revised, or rejected the proposal.

## Upstream update policy

`vcep-classification-skills` will be a Git submodule after its licensing and
remediation branch are suitable for a reproducible pin.

An update automation may:

1. fetch the upstream default branch;
2. identify the old and proposed commits;
3. update only the submodule pointer in a branch;
4. run structural, regression, and clinical-safety evals;
5. open a pull request containing commit comparison and test results.

It must never auto-merge. Upstream code stays immutable inside the submodule;
plugin-specific changes belong in adapters owned by the main repository.

## Release gates

The local preview may proceed once the three initial fixtures pass. A public
release additionally requires:

- explicit licenses for bundled/copied code and data;
- documented privacy and data-retention behavior for every remote service;
- secure configuration for any API credentials introduced later;
- pinned reference/guideline versions;
- representative positive, negative, VUS, CNV, liftover, multilingual, and
  tool-failure evaluations, including ambiguous and mixed-layout variant tables;
- independent clinical review of workflow language and stop conditions.
