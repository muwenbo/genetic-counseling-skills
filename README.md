# Rare-Disease Genetic Counseling Plugin

Contract-first development workspace for an installable Codex plugin supporting
rare-disease constitutional/germline genetic counseling.

The first release is a local developer preview. It will orchestrate existing
variant, CNV, phenotype, disease-ranking, and literature capabilities without
treating automated output as a clinical verdict.

Current design artifacts:

- `docs/architecture.md` — component boundaries and integration policy
- `docs/skill-contracts.md` — user-facing workflow contracts for the first eight skills
- `docs/rest-api-contracts.md` — REST endpoints wrapped by the skills
- `plugins/rare-disease-genetic-counseling/schemas/case-context.schema.json` — shared phenotype and case representation
- `plugins/rare-disease-genetic-counseling/schemas/interpretation-proposal.schema.json` — auditable classification and hypothesis output
- `plugins/rare-disease-genetic-counseling/schemas/variant-table-review.schema.json` — auditable laboratory-table inspection and mapping
- `evals/manifest.json` — acceptance fixtures derived from independent examples

The skills-only plugin scaffold and repo-local marketplace are installed for
developer preview. REST clients are not connected yet; the contracts and
acceptance behavior should be reviewed first.

Validate fixture integrity with:

```bash
python3 evals/check_fixtures.py
```
