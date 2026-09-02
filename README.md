# Rare-Disease Genetic Counseling Plugin

An installable AI-agent plugin for review-centered rare-disease constitutional
and germline genetic counseling workflows. It helps structure English or Chinese
case narratives, review variant tables and annotated callsets, rank disease
candidates, interpret sequence variants and CNVs, find literature, assess
negative or uncertain results, draw pedigrees, and draft counseling summaries.

> [!IMPORTANT]
> This plugin provides clinical decision support, not autonomous diagnosis.
> Classifications, candidate rankings, reports, and recommendations are
> reviewable proposals that require a qualified genetics professional. Do not
> use it for emergencies, somatic oncology, pharmacogenomics, or independent
> treatment decisions.

## Install without a command line

No programming is required. Once the public release is available, in Codex open
the **Plugins** directory in the ChatGPT desktop app, search for **Rare Disease
Genetic Counseling**, select the **+** button, and start a new chat after
installation. In Claude Cowork, open
**Customize → Plugins → + → Add marketplace**, paste
`https://github.com/muwenbo/genetic-counseling-skills`, then select this plugin
and choose **Install**. These steps follow the current
[OpenAI plugin instructions](https://learn.chatgpt.com/docs/plugins) and
[Claude Cowork plugin instructions](https://claude.com/docs/cowork/guide/plugins).

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

The plugin has no connection to a clinical record system and does not write
results to one. Clinical narratives and local files remain local by default.
When a scientific service is needed, the workflow minimizes the disclosed
payload and records the service, operation, version, warnings, and failures.

## Developer setup

Clone the repository and initialize the pinned upstream dependency:

```bash
git submodule update --init --recursive
```

Developer checkouts use the pinned submodule for sequence annotation and VCEP
lookup. Clean plugin installations can, after explicit user approval, fetch and
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
