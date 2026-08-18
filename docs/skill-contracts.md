# Skill contracts

These contracts define behavior before individual `SKILL.md` files are
scaffolded. All outputs are proposals unless a contract explicitly describes a
confirmed read from a source system.

## Shared conventions

Every skill accepts or produces the shared case model in
`../plugins/rare-disease-genetic-counseling/schemas/case-context.schema.json`
when case evidence is involved. Interpretive outputs use
`../plugins/rare-disease-genetic-counseling/schemas/interpretation-proposal.schema.json`.

Every response must distinguish:

- facts supplied by the user or record;
- normalized representations;
- tool-derived evidence;
- model inference;
- missing information;
- actions requiring human confirmation.

The public plugin has no clinical-record integration. It returns reviewable
artifacts to the user and does not write case data or interpretations to an
external clinical system.

## `prepare-rare-disease-case`

**Goal:** Turn an English or Chinese clinical narrative into a reviewable rare-
disease case context without diagnosing the proband.

**Inputs**

- narrative text;
- optional age, sex, assay type, family history, and known genome build;
- optional existing HPO terms.

**Workflow**

1. Locally separate findings, explicit negatives, suspected diagnoses,
   historical events, treatments/exposures, and family history.
2. Preserve source spans or short source excerpts for reviewer traceability.
3. Convert unambiguous numeric laboratory values to named abnormalities only
   when reference range, unit, and age context support the conversion.
4. For Chinese or mixed-language findings, translate each minimized finding
   locally into an English retrieval phrase while keeping assertion, certainty,
   and temporality outside the phrase.
5. Check each English phrase for semantic equivalence. Send an unambiguous,
   agent-verified phrase to vector search at
   `POST https://rdkg.viknox.com.cn/hpo/search`; request reviewer resolution only
   when ambiguity could materially change the HPO mapping. Never send raw
   Chinese narrative.
6. Retain exactly one proposed HPO term per finding, keeping alternatives for
   audit rather than submitting all candidates.
7. Check obsolete/replaced and graph-dead terms when the knowledge graph is
   available.
8. Present findings, translation dispositions, and HPO proposals for review.

**Outputs**

- `case_context`;
- accepted and unresolved HPO proposals;
- English retrieval phrases and verification dispositions;
- confounders and missing-data questions;
- provenance and extractor limitations.

**Stop or qualify when**

- a finding cannot be separated from a diagnosis or negation scope;
- numeric laboratory context is insufficient;
- an HPO candidate changes the meaning of the source phrase;
- an English retrieval phrase is ambiguous or changes specificity and the agent
  cannot resolve the intended meaning from local context;
- the narrative contains identifiers that a proposed remote call does not need.

**Must not** diagnose, treat unmentioned findings as absent, or promote a
suspected infection or syndrome to an observed fact.

## `review-variant-table`

**Goal:** Inspect an untrusted testing-company Excel, CSV, or TSV germline
variant export and produce a reviewer-approved scientific mapping and variant
inventory without accepting the company's interpretation as verified.

**Inputs**

- local `.xlsx`, `.csv`, or `.tsv` file;
- optional assay, sample-role, genome-build, and coordinate information;
- optional laboratory legend or export documentation;
- optional phenotype context for later shortlisting.

**Workflow**

1. Keep the source local and compute a file hash without retaining the filename.
2. Inventory sheets by pseudonymous reference, dimensions, hidden state, merged
   cells, formulas, and candidate header rows without mutating the workbook.
3. Propose the selected sheet, header, data range, row meaning, sample scope, and
   source-to-canonical column mapping.
4. Require human review before extraction. Never fall back to the first sheet or
   first row when parsing is ambiguous or malformed.
5. Extract only approved scientific columns with source sheet/row lineage.
   Exclude direct identifiers and label company classifications, filters, ACMG
   codes, frequencies, and database assertions as supplied.
6. Establish explicit genome build and coordinate convention before genomic
   normalization or classification. Preserve incomplete and ambiguous alleles.
7. Reconcile accepted, unresolved, rejected, and blank rows against the examined
   range. Record a reason for every unresolved or rejected nonblank row.
8. Route reviewer-selected records to disease ranking or individual sequence/CNV
   classification without collapsing the table into a diagnostic conclusion.

**Outputs**

- `variant_table_review` artifact;
- workbook inventory and reviewed selection;
- source-to-canonical mappings;
- normalized scientific records with row lineage and dispositions;
- row reconciliation, blocking issues, missing context, and provenance;
- downstream routing recommendations.

**Hard stops:** unresolved sheet/header/range, missing sample discriminator for a
mixed table, missing build or coordinate convention where required, ambiguous
REF/ALT or transcript meaning, direct identifiers that cannot be excluded,
parser failure, or row-count mismatch.

**Must not** upload raw workbook previews to a separate model, log filenames or
identifiers, execute macros, overwrite the source, silently delete variants,
equate a laboratory filter with benignity, infer that an absent gene was tested,
or classify the entire table without variant-level review.

## `rank-disease-candidates`

**Goal:** Produce phenotype-only disease candidates or variant-backed gene and
disease candidates, clearly identifying which mode was used.

**Inputs**

- reviewed positive HPO terms;
- optional explicitly negative HPO terms;
- optional observed gene symbols or annotated variants;
- requested mode: `phenotype_only`, `variant_backed`, or `both`.

**Workflow**

1. Validate HPO identifiers and polarity.
2. When an HPO term came from Chinese text, require its agent-verified or
   reviewer-resolved English retrieval phrase in the audit trail; never re-query
   the raw Chinese phrase.
3. For phenotype-only mode, call the public knowledge graph at
   `https://rdkg.viknox.com.cn` and inspect both score and support selection arms.
4. For variant-backed mode, use prioritization results and expose phenotype,
   genotype, inheritance, phase, and skipped-variant evidence.
5. Reconcile the two lists without collapsing them into one opaque score.
6. Explain coverage limitations and evidence conflicts.

**Outputs**

- ranked candidates with mode and evidence chain;
- matched and contradictory phenotypes;
- inheritance and gene context;
- coverage warnings and unresolved alternatives.

**Stop or qualify when** no positive phenotype exists, graph coverage is
insufficient, the assay/variant set is incomplete, or rankings are stale.

**Must not** claim associated genes were tested, call a diagnosis solely from a
rank, or interpret an unreturned disease as excluded.

## `classify-sequence-variant`

**Goal:** Build an auditable ACMG/AMP and applicable VCEP classification
proposal for one constitutional sequence variant and one disease context.

**Inputs**

- variant in genomic, transcript HGVS, gene coding, protein, or rsID form;
- explicit genome build for genomic input;
- disease and inheritance context;
- transcript context or permission to propose one;
- optional case, segregation, phase, and literature evidence.

**Workflow**

1. Parse without changing the asserted variant.
2. Require genome build for genomic coordinates.
3. Verify the pinned `vcep-classification-skills` dependency and exact commit.
   Dependency failure is not an empty annotation.
4. Normalize to GRCh38 and verify chromosome, position, REF, and ALT against a
   reference source; preserve the original representation.
5. Reuse upstream `vep_annotate.py` through the local safety adapter. Preserve
   the returned annotation and do not treat VEP as independent REF verification.
6. Resolve transcript, gene, disease, inheritance, zygosity, and phase gaps.
7. Retrieve additional population evidence without converting missing fields to
   absence.
8. Reuse upstream `check_vcep_spec.py` and registry, then select the applicable
   VCEP document by gene, disease, and inheritance;
   record its version and submodule commit.
9. Evaluate all criteria as `met`, `not_met`, `not_applicable`, or
   `not_evaluated`, with strength and evidence provenance.
10. Do not use upstream `classify_variant.py`; compare only a separately
    validated engine output with the independently assembled proposal.
11. Present the proposal and unresolved evidence for human review.

**Outputs**

- normalized variant and validation status;
- `classification_proposal` with criteria and point tally;
- engine comparison;
- missing evidence and review questions.

**Hard stops**

- missing genomic build;
- REF mismatch or ambiguous/multiple normalization without disambiguation;
- missing disease/inheritance context where it affects criteria or VCEP choice;
- unreliable liftover;
- unsupported mitochondrial, mosaic, complex, or structural representation.

**Must not** apply PVS1 from consequence alone, use absence from gnomAD as proof
of pathogenicity, infer phase or de novo status, or submit a classification.

## `classify-cnv`

**Goal:** Apply the ACMG/ClinGen constitutional CNV point metric through the CNV
Classification API and turn the response into a reviewable proposal.

**Inputs**

- chromosome, 1-based inclusive start/end, loss/gain, and explicit genome build;
- optional reviewed HPO, inheritance, reported case, segregation, and case-
  control evidence.

**Workflow**

1. Parse and show the inclusive size calculation.
2. Require and echo the genome build and coordinate convention.
3. Separate proband evidence from literature/reported-case evidence.
4. Send a minimal batched request to `POST /api/v1/classify`.
5. Preserve all section scores, category hits, point ranges, pending evidence,
   and liftover fields.
6. Refuse to interpret a failed liftover as a classification.
7. Present the tier as an automated proposal with limitations.

**Outputs**

- normalized/scored coordinates and size;
- classification, total points, section scores, and evidence trail;
- liftover result;
- missing evidence and review questions.

**Hard stops:** missing build, invalid coordinates/type, failed liftover, or
inconsistent evidence representations.

**Must not** send raw narrative or identifiers, convert a null classification
to VUS, or imply the service is validated for autonomous diagnostic use.

## `find-variant-literature`

**Goal:** Discover and retrieve literature relevant to a variant, gene-disease
pair, ACMG criterion, or CNV region, then extract claim-level evidence.

**Inputs**

- one or more of: normalized variant, HGVS, rsID, gene, disease, region, PMID;
- evidence question such as functional effect, segregation, de novo cases,
  phenotype specificity, PM3, PS4, or benign evidence;
- date/language/full-text preferences.

**Workflow**

1. Build a reproducible discovery query when PMIDs are not already known.
2. Preview bibliographic metadata and deduplicate identifiers.
3. Ask before retrieving a large or nonessential full-text set.
4. Retrieve lawful PubMed/PMC content; otherwise use citation/abstract metadata.
5. Extract structured claims with population, assay, counts, phase, phenotype,
   and limitations.
6. Separate paper statements from classification interpretation.

**Outputs**

- query and result inventory;
- selected papers and access status;
- claim-level evidence with PMID/DOI and location;
- relevance and applicability limitations.

**Stop or qualify when** variant nomenclature is ambiguous, disease context is
missing, full text is unavailable, or a paper does not identify the asserted
allele/case relationship.

**Must not** invent full-text evidence, treat a review as primary case evidence,
or store/distribute copyrighted full text beyond allowed access.

## `interpret-negative-or-vus`

**Goal:** After completed variant analysis, generate restrained hypotheses for
assay-blind mechanisms and prioritize appropriate orthogonal testing.

**Inputs**

- reviewed negative or VUS result;
- assay type and QC/coverage status;
- reviewed phenotype gestalt;
- optional partial molecular clue.

**Workflow**

1. Confirm the negative is not explained by failed QC or inadequate coverage.
2. Define blind spots for the actual assay.
3. Generate at most three phenotype-specific hypotheses whose mechanisms could
   plausibly be missed by that assay.
4. Rank hypotheses by specificity and consistency, not by narrative appeal.
5. Name an orthogonal confirmatory test and why it addresses the mechanism.

**Outputs**

- hypothesis proposals, never findings;
- phenotype-to-mechanism reasoning;
- prioritized confirmatory tests;
- limitations and alternatives.

**Hard stops:** analysis incomplete, QC failure not resolved, assay unknown, or
phenotype too nonspecific for a targeted hypothesis.

**Must not** manufacture a diagnosis to rescue a negative result or route a
hypothesis into a primary finding.

## `draft-counseling-summary`

**Goal:** Convert reviewed findings and proposals into a clear pre-/post-test
genetic-counseling draft for professional review.

**Inputs**

- reviewed case context;
- result type: positive, VUS, negative, carrier/secondary only when in scope;
- reviewed sequence/CNV proposal and disease context;
- family structure and audience/language preferences;
- approved recommendations.

**Workflow**

1. State what was tested and its limitations.
2. Separate molecular result, clinical interpretation, uncertainty, and family
   implications.
3. Explain inheritance and recurrence only to the resolution supported by the
   family data and diagnosis.
4. Describe recommended confirmation, segregation, or follow-up testing.
5. Produce clinician-facing and optional patient-facing versions without
   changing the evidentiary meaning.
6. Mark the draft as requiring qualified review.

**Outputs**

- result summary;
- evidence and uncertainty statement;
- inheritance/family implications;
- follow-up questions and recommendations;
- assay limitations and review status.

**Stop or qualify when** the classification is unreviewed, disease association
or inheritance is unresolved, family relationships are inferred, or recurrence
risk would require missing penetrance/parental information.

**Must not** provide a definitive diagnosis from a VUS, give unsupported numeric
recurrence risk, or present automated text as a signed clinical report.
