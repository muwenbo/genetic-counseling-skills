# Rare-Disease Genetic Counseling Plugin — Agent Guide

This repository develops a public, installable collection of AI-agent skills
for rare-disease constitutional/germline genetic counseling. The same skills
are packaged for compatible GUI-based agents through platform metadata. Treat
them as clinical decision support: outputs are reviewable proposals, never
autonomous diagnoses, classifications, signed reports, or treatment
instructions.

## Start here

Before changing behavior, read the relevant sources in this order:

1. `AGENTS.md` (this file)
2. `README.md`
3. `docs/architecture.md`
4. `docs/skill-contracts.md`
5. `docs/rest-api-contracts.md`
6. The affected `plugins/rare-disease-genetic-counseling/skills/*/SKILL.md`
7. Its directly referenced files under `references/`, `assets/`, or `scripts/`

Use `rg` and `rg --files` for discovery. Check repository status before editing
when a Git worktree is present, and preserve unrelated user changes.

## Product scope

The first release covers rare-disease constitutional/germline counseling:

- structuring English or Chinese case narratives and proposing HPO terms;
- inspecting and normalizing testing-company variant tables without trusting
  company annotations as independently verified;
- filtering large local annotated germline callsets with reviewer-approved
  fields and thresholds;
- phenotype-only disease candidate ranking;
- review-centered sequence-variant classification;
- ACMG/ClinGen constitutional CNV classification;
- variant and gene-disease literature review;
- restrained interpretation of negative or VUS results;
- drafting clinician-facing and optional patient-facing counseling summaries;
- drawing reviewable pedigree data and figures from user-supplied family facts.

Out of scope for v1 are somatic oncology, pharmacogenomics, polygenic risk,
standalone carrier or newborn-screening workflows, autonomous diagnosis, and
clinical-record management.

The plugin is intended for the general public. **Do not introduce Noxia
dependencies, Noxia terminology, case mutations, report writes, or assumptions
about access to a private clinical system.** User-supplied exported data may be
accepted as input, but the plugin must remain system-independent.

## Repository map

```text
.
├── README.md                              # English public documentation
├── README.zh-CN.md                        # Simplified Chinese documentation
├── .agents/plugins/marketplace.json       # repo-local developer marketplace
├── .claude-plugin/marketplace.json        # Claude-compatible marketplace
├── docs/
│   ├── architecture.md                    # boundaries and integration policy
│   ├── skill-contracts.md                 # user-facing workflow contracts
│   └── rest-api-contracts.md              # actual REST endpoint contracts
├── evals/                                 # independent acceptance fixtures
└── plugins/rare-disease-genetic-counseling/
    ├── .codex-plugin/plugin.json
    ├── .claude-plugin/plugin.json
    ├── schemas/
    └── skills/
```

Planned upstream resources belong under `vendor/` as pinned Git submodules.
Do not copy or modify upstream source inside this repository when a thin local
adapter can own the integration behavior.

## Architecture decisions

- Skills wrap scientific REST APIs directly. There is no plugin-owned MCP
  gateway.
- Use the real endpoint names in instructions, clients, logs, and provenance.
  Do not invent duplicate operations such as `get_capabilities`,
  `get_hpo_term`, or `rank_disease_candidates`.
- A small bundled client may add input validation, privacy filtering, timeouts,
  bounded retries, and response preservation. It must not hide or reinterpret
  the upstream clinical contract.
- Keep service base URLs configurable unless a stable public URL is documented.
- Keep finding extraction and clinical-text handling local by default. Send
  only minimized scientific inputs to remote services.
- An unavailable or unsupported API capability is not an empty or negative
  clinical result.

### Knowledge-graph REST flow

- Public base URL: `https://rdkg.viknox.com.cn`
- Public skills use this HTTPS endpoint; do not document or route users to a
  loopback development service.

The knowledge graph is stateless and does not extract findings or diagnose:

```text
clinical narrative
  -> skill extracts short positive and explicitly negative findings locally
  -> Chinese/mixed findings are translated locally into English search phrases
  -> agent verifies semantic equivalence or requests review for material ambiguity
  -> POST /hpo/search
  -> GET /hpo/terms/{hp_id}
  -> POST /candidates
  -> skill explains and qualifies the returned candidates
```

Use `GET /healthz` for health, versions, and capability information. Preserve
assertion polarity outside `/hpo/search`. Use one reviewed HPO term per finding;
alternates are audit candidates, not extra patient observations. Inspect
`n_annotated_diseases` before graph ranking, and treat graph-dead terms and
unannotated diseases as coverage gaps rather than negative evidence.

### CNV Classification API

- Base URL: `https://cnvclassifier.viknox.com/`
- Health: `GET /health`
- Classification: `POST /api/v1/classify`
- Coordinates are 1-based and inclusive.
- Require an explicit `hg19` or `hg38` input even though the service defaults to
  hg38.
- Batch variants and stay below 120 requests/minute/IP.
- Preserve section scores, evidence, suggested ranges, pending evidence, and
  liftover output exactly.
- A refused hg19 lift has `classification: null`; never convert it to VUS or
  score the original coordinates as hg38.

## Clinical correctness boundaries

These rules are non-negotiable:

1. Require genome build for genomic coordinates. Do not inherit an upstream
   default.
2. Verify coordinates and alleles together. Positional liftover alone does not
   verify REF/ALT on the target assembly.
3. Resolve disease and inheritance context before applying context-dependent
   ACMG/AMP or VCEP criteria.
4. Preserve phenotype polarity and certainty: unmentioned is not absent;
   suspected is not observed; historical is not necessarily current.
5. Never silently upgrade missing parentage, phase, segregation, functional, or
   phenotype-specificity evidence.
6. Treat API tiers, point totals, evidence codes, rankings, and model-generated
   prose as proposals requiring qualified human review.
7. Never coerce a service failure, null result, unavailable capability, or
   unimplemented criterion into VUS, no match, or `not_met`.
8. Do not diagnose from a candidate rank, claim an associated gene was tested,
   or infer a variant, relative, genotype, de novo status, or phase.
9. Do not send Chinese clinical text directly to public graph retrieval.
   Translate each minimized finding locally and preserve assertion metadata
   outside the phrase. The agent may disclose a semantically clear English
   phrase; request review only when material ambiguity remains.

When evidence is insufficient, stop or qualify the result and state exactly
what information or capability is missing.

## Privacy and data handling

- Assume clinical narratives, family histories, dates, laboratory results,
  pedigrees, VCFs, reports, and case exports may contain sensitive health data.
- Do not print, log, commit, upload, or retain direct identifiers.
- Raw narrative stays local unless the user explicitly authorizes a suitable
  remote service and the service contract requires it.
- Scientific coordinates, gene symbols, HPO IDs, and publication identifiers
  may be sent only after validation and payload minimization.
- Never expose `.env` values, credentials, tokens, database dumps, or private
  service configuration. Document configuration with placeholders only.
- Record which fields were disclosed to a remote service without recording the
  sensitive values themselves.

## Skill development rules

- A user-facing workflow is a skill directory containing a valid `SKILL.md`.
- Keep YAML front matter limited to `name` and `description` unless the Codex
  skill format explicitly adds another supported field.
- Put essential trigger wording in `description`; put workflow and safety
  instructions in the body.
- Keep `SKILL.md` focused. Move detailed API schemas, clinical guardrails, and
  reusable templates into directly referenced `references/` or `assets/` files.
- Read a referenced clinical guideline or guardrail fully before applying it.
- Reuse the shared schemas in `plugins/rare-disease-genetic-counseling/schemas/`
  rather than creating incompatible per-skill representations.
- Preserve provenance: service/repository, endpoint/operation, version or Git
  commit, retrieval time, declared assembly and coordinate convention,
  warnings, failures, missing fields, and reviewer disposition.
- Update the relevant contract document and add or revise an evaluation fixture
  whenever behavior changes materially.

The initial skills are:

- `prepare-rare-disease-case`
- `review-variant-table`
- `filter-variant-callset`
- `rank-disease-candidates`
- `classify-sequence-variant`
- `classify-cnv`
- `find-variant-literature`
- `interpret-negative-or-vus`
- `draft-counseling-summary`
- `draw-pedigree`

## Upstream repositories

`variant-classifier` and `paper-finder` from
`muwenbo/vcep-classification-skills` are intended to be consumed through a
single pinned Git submodule under `vendor/vcep-classification-skills`.

The developer preview pins commit
`05bf1f6bce4e6be04f9e52b55db1d5fee03029d9`. Sequence annotation and VCEP lookup
may reuse the upstream scripts only through the plugin-owned safety adapter.
Do not invoke upstream `classify_variant.py` as a clinical classifier; its PVS1,
PM2, and evidence-state behavior does not meet this repository's guardrails.

Because a root-level submodule is not included in a clean plugin installation,
the safety adapter may offer a first-use setup operation. It must require
explicit user approval, fetch only the exact pinned public Git commit into a
non-clinical local cache, verify the commit, required files, and MIT license,
avoid overwriting an existing conflicting target, and disclose no clinical data
during setup. A declined or failed setup is a capability failure.

For upstream updates:

1. Fetch upstream and identify the old and proposed commits.
2. Update only the submodule pointer on a dedicated branch.
3. Run structural, regression, and clinical-safety evaluations.
4. Open a pull request containing the commit comparison, upstream changes, and
   validation results.
5. Require human review; never auto-merge an upstream update.

Keep plugin-specific adapters and safety behavior in this repository. Do not
patch vendored source in place. Confirm licensing before adding or distributing
upstream code, documents, or data.

Relevant sibling sources may exist under
`/Users/tiger/Developer/variant-analyzer`. Treat them as reference material
unless the task explicitly authorizes a cross-repository change. Read each
sibling project's own `AGENTS.md` or `CLAUDE.md` before touching it.

## Verification

Run the smallest relevant checks, then the full plugin checks before handoff.

```bash
# Independent acceptance fixtures
python3 evals/check_fixtures.py

# Validate every skill
for skill_dir in plugins/rare-disease-genetic-counseling/skills/*; do
  python3 /Users/tiger/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill_dir"
done

# Validate the plugin manifest and layout
python3 /Users/tiger/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/rare-disease-genetic-counseling
```

For REST client changes, add focused tests covering input validation, build and
coordinate handling, response preservation, timeouts, rate limits, malformed
responses, and the distinction between service failure and empty clinical
results. Do not use identifiable clinical data in tests.

## Updating the installed developer preview

After changing installed plugin content:

```bash
python3 /Users/tiger/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py \
  plugins/rare-disease-genetic-counseling

codex plugin add rare-disease-genetic-counseling@personal
```

Revalidate after updating the cachebuster. Tell the user to start a new Codex
thread so the refreshed skills are loaded.

## Change discipline

- Keep changes inside this repository unless the user explicitly requests a
  sibling-project change.
- Do not commit, push, publish, open a pull request, call production services,
  or mutate external systems unless the task explicitly requests it.
- Preserve unrelated local changes and generated artifacts.
- If code, documentation, and deployed API behavior disagree, verify the live
  contract safely and report the discrepancy instead of silently choosing one.
- In handoff, list the files changed, validations run, and any untested external
  dependency or unresolved clinical assumption.
