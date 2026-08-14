# REST API contracts

The public plugin wraps scientific REST services directly inside its skills.
There is no plugin-owned MCP gateway and no Noxia dependency. Bundled client
scripts may provide validation, timeouts, retries, and response preservation,
but they must not rename the underlying clinical operations into a second API.

## Shared integration rules

- Keep each service base URL configurable unless a public URL is documented.
- Require explicit genome build whenever genomic coordinates are supplied.
- Send the minimum required payload; do not send raw narrative or direct
  identifiers to scientific services.
- Record the service, endpoint, retrieval time, request fields sent, version
  information returned by the service, warnings, and failures.
- Distinguish an unavailable service or unsupported capability from an empty
  clinical result.
- Use bounded timeouts. Retry only transient failures and rate-limit responses;
  never retry validation failures as if they were transport failures.

## Knowledge-graph API

The developer instance documented by `rd-knowledge-graph` uses
`http://127.0.0.1:8100`. The public plugin must use a configurable base URL
because no public deployment URL has been specified.

The service is stateless. It maps short phrases to HPO terms and HPO terms to
ranked disease candidates; it does not extract findings from a narrative and
does not diagnose the patient.

### `GET /healthz`

Returns artifact versions and whether the optional full graph database is
attached. Skills may use this endpoint for readiness and provenance. It replaces
the previously proposed `get_capabilities` abstraction; no separate capability
tool is needed.

### `POST /hpo/search`

Maps up to 50 short English or Chinese clinical phrases to HPO candidates.

```json
{
  "queries": ["absent right thumb", "malar hypoplasia"],
  "k": 5,
  "score_threshold": 0.75
}
```

The skill extracts findings locally, keeps assertion polarity locally, and sends
only minimized phrases. It uses exactly one reviewed HPO term per phrase; the
remaining candidates are alternatives for audit, not additional patient facts.
Scores between plausible and incorrect matches overlap, so a score is not a
correctness test.

### `GET /hpo/terms/{hp_id}`

Returns the term name, definition, synonyms, parents, children, obsolete and
replacement status, information content, and `n_annotated_diseases`.

This endpoint is what earlier drafts called `get_hpo_term`. That name is not a
separate public skill or tool. The case-preparation and disease-ranking skills
call the endpoint internally to avoid obsolete terms and graph-dead terms. A
term with zero annotated diseases cannot contribute useful graph evidence; this
is a coverage limitation, not a negative patient finding.

### `POST /candidates`

Ranks diseases from reviewed positive and explicitly absent HPO terms.

```json
{
  "positive": [{"hp_id": "HP:0009777", "confidence": 0.9}],
  "negative": [{"hp_id": "HP:0000501", "confidence": 1.0}],
  "gene_symbols": ["SF3B4"],
  "limit": 50,
  "detail": "standard"
}
```

This endpoint is the operation performed by the `rank-disease-candidates`
skill. The earlier snake-case name `rank_disease_candidates` was only a proposed
wrapper function and is removed. The skill must inspect both `score` and
`support` selection arms, relations, contradictions, unresolved gene symbols,
normalized HPO identifiers, and the coverage report. Associated genes are graph
context and must not be presented as patient observations or tested genes.

### Optional graph inspection

- `POST /graph/subgraph` returns raw graph retrieval without scoring.
- `POST /graph/neighbors` performs edge lookup. A `503` for predicates outside
  the curated slice means the capability is unavailable, not that no edge
  exists.

### Knowledge-graph error semantics

| Status | Meaning | Skill behavior |
|---|---|---|
| `400` | Empty positive phenotype list | Stop; this is not a negative ranking |
| `404` | Unknown HPO ID | Correct or review the identifier |
| `413` | Request batch too large | Respect the documented request limits |
| `422` | Unknown/unusable HPO IDs | Review the returned identifiers |
| `503` | Requested graph capability unavailable | Report a capability gap |

## CNV Classification API

Base URL: `https://cnvclassifier.viknox.com/`

### `GET /health`

Checks service availability. Do not send case data to this endpoint.

### `POST /api/v1/classify`

Applies the ACMG/ClinGen 2020 Riggs point metric to one or more CNVs. Coordinates
are 1-based and inclusive. The skill requires `genome_build` even though the API
defaults to hg38.

```json
{
  "variants": [
    {
      "chrom": "chr22",
      "start": 19000000,
      "end": 21500000,
      "cnv_type": "loss",
      "genome_build": "hg38",
      "hpo_terms": [],
      "inheritance": "unknown",
      "phenotype_consistency": "unknown",
      "reported_cases": [],
      "reported_segregation": null,
      "case_control_studies": []
    }
  ]
}
```

Batch variants in one request and remain below 120 requests per minute per IP.
Preserve the input-aligned classification, total points, section scores, every
evidence item, suggested ranges, pending evidence, and liftover result. If an
hg19-to-hg38 lift is refused, classification remains `null`; never convert it to
VUS or score the original coordinates as hg38.

## Other integrations

Variant-table inspection and extraction do not call a REST service. The
`review-variant-table` skill uses a bundled local script, retains a file hash and
pseudonymous sheet/row lineage, and sends no workbook preview to a separate
model or scientific API. A parser failure or unresolved mapping is not an empty
variant result.

Sequence normalization, sequence evidence classification, and literature
discovery/retrieval will follow the same direct-service pattern once their
public contracts are selected. `vcep-classification-skills` and `paper-finder`
remain upstream skill resources pinned by Git submodule commit, not operations
on a plugin-owned gateway.
