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

## `filter-variant-callset`

**Goal:** Filter a large, locally stored annotated germline WES/WGS callset into a
reviewable variant shortlist using reviewer-approved criteria, producing a
`variant_prioritization` result without accepting the shortlist as a diagnosis.

**Inputs**

- local annotated `.vcf`/`.vcf.gz`, `.tsv`, `.csv`, or `.xlsx` callset;
- explicit genome build;
- reviewer-approved field mapping and thresholds (frequency, consequence, gene
  panel, quality, candidate zygosity), resolved against annotations already in
  the file.

**Workflow**

1. Keep the callset local; compute a file hash without retaining the filename.
2. Inspect the callset for format, variant count, chromosome coverage, sample
   columns, and candidate annotation fields without mutating the source. Propose
   field specs; never select one automatically.
3. Require human review of the field mapping and thresholds before filtering.
   Stop on an ambiguous field rather than guessing.
4. Apply only reviewer-approved deterministic filters. Treat a variant lacking a
   frequency annotation as unknown frequency, never as rare or common by default.
5. Emit a stage-by-stage funnel and excluded-class counts so no variant class is
   silently dropped; the source is never rewritten.
6. Route the shortlist to `rank-disease-candidates` variant_backed as an imported
   prioritization result, keeping the filter funnel separate from any ranking.

**Outputs**

- `variant_prioritization` artifact with file hash, genome build, and parameters;
- shortlisted candidates with supplied annotations preserved and labeled;
- stage funnel, unknown-frequency count, and excluded-class counts;
- downstream routing recommendation.

**Hard stops:** missing genome build, an annotation field for a requested filter
that cannot be resolved unambiguously, frequency or consequence filtering
requested on a callset without that annotation, mixed samples or builds without a
reliable discriminator, a funnel that does not reconcile, malformed parser
output, a file that is a curated laboratory report table (route to
`review-variant-table`), or a parser failure mistaken for an empty callset.

**Must not** add annotations not present in the file, contact the network, upload
the callset or rows to a separate model or service, log filenames or identifiers,
overwrite the source, silently delete a variant class, treat an unannotated
variant as rare or common, infer phase, segregation, compound heterozygosity, or
de-novo status, run automatically as a fallback within disease ranking, or treat
a gene absent from the shortlist as adequately assessed.

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

0. When only coordinate conversion is requested, accept one simple VCF-style
   SNV/indel and explicit source/target builds without requiring disease context.
   Verify and normalize source REF, require one contiguous Ensembl assembly
   mapping, handle strand, verify and normalize target REF/ALT, and require a
   concordant reverse mapping. Return a conversion artifact, not a classification.
1. Parse without changing the asserted variant.
2. Require genome build for genomic coordinates.
   Treat genomic RefSeq HGVS (`NC_...:g.`) as genomic input and normalize it to
   one verified VCF-style allele before bundled annotation; stop if that
   normalization capability is unavailable.
3. Verify the pinned `vcep-classification-skills` dependency and exact commit.
   Dependency failure is not an empty annotation.
4. For genomic input, route GRCh38 and GRCh37 coordinates to their matching
   Ensembl REST endpoints without implicit liftover. Verify chromosome,
   position, REF, and ALT on the declared assembly with a reference-sequence
   request separate from VEP, and preserve the original representation.
5. When Ensembl explicitly rejects a versioned RefSeq transcript HGVS as
   unresolved,
   map it through NCBI Variation contextual SPDI to exactly one canonical GRCh38
   genomic allele. Preserve the asserted and mapped representations; never
   replace a transcript version suffix or infer equivalence from c. coordinates.
   A timeout, malformed response, rate limit, or execution failure remains an
   Ensembl service failure and does not trigger NCBI disclosure.
6. Reuse upstream `vep_annotate.py` through the local safety adapter. Preserve
   the complete returned annotation and do not treat VEP as independent REF
   verification. Quarantine any classification-shaped fields from clinical
   interpretation while keeping them in the raw response.
7. Resolve transcript, gene, disease, inheritance, zygosity, and phase gaps.
8. Retrieve additional population evidence without converting missing fields to
   absence.
9. Reuse upstream `check_vcep_spec.py` and registry, then select the applicable
   VCEP document by gene, disease, and inheritance;
   record its version and submodule commit.
10. Evaluate all criteria as `met`, `not_met`, `not_applicable`, or
   `not_evaluated`, with original and effective strength, signed point effect,
   rationale, confirmation status, and evidence provenance. Keep zero-point
   criteria visible.
11. Do not use upstream `classify_variant.py`; compare only a separately
    validated engine output with the independently assembled proposal.
12. Present a criterion table by default, followed by the scoring
    framework/version, pathogenic and benign subtotals, signed total, tier
    threshold, rule-based ACMG/AMP combination, proposed tier, and unresolved
    evidence for human review. Use an applicable VCEP point system when one is
    specified; otherwise label the Tavtigian et al. 2020 Bayesian ACMG/AMP point
    calibration. Surface
    disagreements between point and combining-rule results and avoid correlated
    double counting.

**Outputs**

- normalized variant and validation status;
- `classification_proposal` with a complete criterion table, signed point
  tally, scoring framework/version, threshold interpretation, and rule-based
  ACMG/AMP combination;
- engine comparison;
- missing evidence and review questions.

**Hard stops**

- missing genomic build;
- genomic HGVS that cannot be normalized to one independently verified
  VCF-style allele;
- REF mismatch or ambiguous/multiple normalization without disambiguation;
- returned VEP assembly differs from the declared genomic build;
- liftover REF mismatch, zero/multiple/split mapping, target-reference
  disagreement, or failed reverse mapping;
- ambiguous transcript-version mapping or mapped/current allele disagreement;
- missing disease/inheritance context where it affects criteria or VCEP choice;
- unreliable liftover;
- unsupported mitochondrial, mosaic, complex, or structural representation.

**Must not** apply PVS1 from consequence alone, use absence from gnomAD as proof
of pathogenicity, infer phase or de novo status, submit a classification, or
represent coordinate-only mapping as a verified allele conversion.

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

## `draw-pedigree`

**Goal:** Convert user-supplied family-history facts into a reviewable PED/JSON
project and, when local browser capabilities permit, a pedigree figure.

**Inputs**

- supplied relatives, relationships, sex, affection, and optional proband,
  deceased, carrier, adoption, twin, consanguinity, or genotype facts;
- optional existing PED or Pedigree Studio JSON project;
- requested output format and figure type.

**Workflow**

1. Preserve supplied facts and represent unstated sex, affection, relationships,
   and genotypes as unknown rather than inferred.
2. Choose PED for structure and affection only; choose JSON when richer pedigree
   annotations are required.
3. Validate PED before rendering and retain reviewable source data in either
   format.
4. When a figure is requested, serve only the bundled, version-pinned Pedigree
   Studio application shell from a temporary server bound to `127.0.0.1` and
   navigate with `http://`; never navigate to the local asset with `file://`.
5. Generate JSON individuals with the complete key set, including an explicit
   `genotypes` object, so the import cannot depend on editor-side defaults.
6. Load the PED/JSON through the application's visible import control with a
   pre-armed file chooser, or use a browser controller's direct file-input upload
   operation without clicking the hidden input. Fit the view and verify labels,
   relationships, affected states, proband marker, and deceased marker against
   the source data.
7. Export a standalone SVG using the application's export control, or — when the
   download cannot be observed — by reading the rendered markup and dimensions and
   assembling the file outside the page; raw inline `outerHTML` is not a valid
   export path, and a screenshot is not an export.
8. Preserve the loaded editor tab as a user-facing deliverable for direct edits,
   then stop the temporary server without closing the self-contained page.
9. If browser or loopback navigation is unavailable, return the validated data
   file and explicitly state that no figure was generated.

**Outputs**

- validated PED or Pedigree Studio JSON;
- exported SVG/PNG, or a screenshot labelled as a preview, only when rendering
  and verification succeeded;
- retained editable Pedigree Studio tab when the browser supports deliverables;
- explicit unknown fields and rendering capability status.

**Stop or qualify when** relationships conflict, required identifiers are not
unique, the PED/JSON is invalid, the selected browser is unavailable, loopback
HTTP is rejected, or the rendered chart cannot be verified.

**Must not** infer relatives, phenotype, genotype, phase, or segregation; place
family data in a URL or served directory; expose the server beyond loopback;
retry with a disallowed URL scheme; upload data to a remote renderer; repeatedly
click the export control when no download event is exposed; describe a screenshot
as an exported SVG or PNG; or describe a rendering failure as an empty or
successfully generated pedigree.
