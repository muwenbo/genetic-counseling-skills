# Rare-Disease Genetic Counseling Skills

English | [简体中文](README.zh-CN.md)

An installable collection of AI-agent skills for review-centered rare-disease
constitutional and germline genetic counseling workflows. It is designed for
GUI-based agent software that supports skills or plugins, such as Codex, Claude
Cowork, and WorkBuddy. It helps structure English or Chinese case narratives,
review variant tables and annotated callsets, rank disease candidates, interpret
sequence variants and CNVs, find literature, assess negative or uncertain
results, draw pedigrees, and draft counseling summaries.

> [!IMPORTANT]
> These skills provide clinical decision support, not autonomous diagnosis.
> Classifications, candidate rankings, reports, and recommendations are
> reviewable proposals that require a qualified genetics professional. Do not
> use them for emergencies, somatic oncology, pharmacogenomics, or independent
> treatment decisions.

## Ask your AI agent to install it

No programming or command line is required. In a GUI-based AI agent that
supports skills or plugins, send the following message:

> Install and configure the **Rare Disease Genetic Counseling** skills from
> <https://github.com/muwenbo/genetic-counseling-skills> for this agent. Use the
> installation method supported by this application. Tell me when the skills
> are ready, what permissions or network access they need, and whether I need
> to restart the application or begin a new conversation.

The agent should handle the application-specific setup and ask for approval
before downloading additional dependencies or making security-sensitive
changes.

## Included workflows

- Prepare a structured rare-disease case and propose reviewable HPO mappings.
- Inspect and normalize laboratory variant tables without trusting supplied
  annotations as independently verified.
- Filter large local annotated germline callsets with reviewer-approved fields
  and thresholds.
- Rank phenotype-only or variant-backed disease candidates while preserving
  coverage gaps and conflicting evidence.
- Build reviewable ACMG/AMP, ClinGen VCEP, and constitutional CNV classification
  proposals.
- Find variant and gene-disease literature and extract claim-level evidence.
- Explain negative or VUS results, assay blind spots, and restrained next-test
  hypotheses.
- Draft clinician-facing and optional patient-facing counseling summaries.
- Create validated pedigree data and reviewable pedigree figures from supplied
  family facts.

The skills have no connection to a clinical record system and do not write
results to one. Clinical narratives and local files remain local by default.
When a scientific service is needed, the workflow minimizes the disclosed
payload and records the service, operation, version, warnings, and failures.

## Developer setup

Clone the repository and initialize the pinned upstream dependency:

```bash
git submodule update --init --recursive
```

Developer checkouts use the pinned submodule for sequence annotation and VCEP
lookup. Clean installations can, after explicit user approval, fetch and
verify the same immutable MIT-licensed commit into a non-clinical local cache.
No case or variant data is included in that setup request.

The knowledge-graph skills use `https://rdkg.viknox.com.cn`. Chinese or
mixed-language findings are translated locally into minimized English phrases
before HPO search; raw narratives and identifiers are not sent.

## Architecture and validation

- `docs/architecture.md` — component boundaries and integration policy
- `docs/skill-contracts.md` — user-facing contracts for the ten workflows
- `docs/rest-api-contracts.md` — REST endpoints wrapped by the skills
- `plugins/rare-disease-genetic-counseling/schemas/` — shared review and
  provenance schemas
- `evals/manifest.json` — independent acceptance fixtures

Run the repository checks described in [AGENTS.md](AGENTS.md). The smallest
fixture-integrity check is:

```bash
python3 evals/check_fixtures.py
```

See [LICENSE](LICENSE) for the repository license and the bundled pedigree
asset's
[third-party notices](plugins/rare-disease-genetic-counseling/skills/draw-pedigree/assets/THIRD_PARTY_NOTICES.md)
for its retained dependency licenses.
