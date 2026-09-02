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

Public base URL: `https://rdkg.viknox.com.cn`

The service is stateless. It maps short phrases to HPO terms and HPO terms to
ranked disease candidates; it does not extract findings from a narrative and
does not diagnose the patient.

### `GET /healthz`

Returns artifact versions and whether the optional full graph database is
attached. Skills may use this endpoint for readiness and provenance. It replaces
the previously proposed `get_capabilities` abstraction; no separate capability
tool is needed.

### `POST /hpo/search`

Performs SapBERT embedding-based vector search over HPO labels and synonyms. The
live health response identifies the embedding model, term and embedding counts,
and vector dimension. The endpoint maps up to 50 short English clinical phrases
to ranked HPO candidates; `k` is limited to 1-25 and `score_threshold` is
optional. The public-plugin contract deliberately does not send Chinese clinical
phrases because live retrieval has not shown reliable Chinese mapping.

```json
{
  "queries": ["absent right thumb", "malar hypoplasia"],
  "k": 5,
  "score_threshold": 0.75
}
```

The skill extracts findings locally and keeps assertion polarity locally. For a
Chinese or mixed-language source, it translates each minimized finding locally
and checks semantic equivalence. The agent sends an unambiguous phrase without a
mandatory human checkpoint. If alternate translations could materially change
the concept, specificity, anatomical site, or negation scope, it requests review
and pauses that finding. It never sends the raw narrative, Chinese source span,
identifiers, or negation wording.

The skill uses exactly one selected HPO term per finding; remaining candidates
are alternatives for audit, not additional patient facts. Vector similarity is
a retrieval signal, not clinical correctness, and a high score does not remove
the need to compare term meaning with the source finding.

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

This endpoint performs graph retrieval and deterministic scoring; it is not the
vector-search step. It is the operation performed by the
`rank-disease-candidates` skill. The earlier snake-case name
`rank_disease_candidates` was only a proposed
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

Sequence annotation reuses pinned upstream `variant-classifier` code through
`scripts/upstream_variant_adapter.py`. Developer checkouts resolve the pinned
submodule. A clean public installation may, only after explicit user approval,
fetch the exact public Git commit from GitHub into a local non-clinical cache.
The adapter verifies the commit, required resources, and MIT license before
making the checkout available, does not overwrite a conflicting cache target,
and sends no clinical input during setup. For HGVS, rsID, and normalized GRCh38
genomic input, upstream `vep_annotate.py` calls Ensembl REST operations under
`https://rest.ensembl.org/vep/human/`. For normalized GRCh37 genomic input, the
local bridge reuses the pinned VEP client and parser against
`https://grch37.rest.ensembl.org/vep/human/`. The adapter requires an explicit
build for every genomic representation, including `NC_...:g.` HGVS. Genomic
HGVS must first be normalized to a verified VCF-style allele. For VCF-style
input, the adapter retrieves reference sequence on the declared assembly and
stops on REF mismatch before VEP. It preserves results on that assembly without
implicit liftover, uses a bounded timeout, preserves the complete upstream JSON
summary, and records the exact Git commit. Classification-shaped fields in the
raw annotation remain preserved but quarantined; they never make the result
classification-ready. It sends only the scientific variant or the minimized
chromosome/coordinates needed for reference verification and no case narrative
or identifiers.

The adapter's `liftover` operation converts one simple VCF-style SNV/indel in
either direction between GRCh37 and GRCh38. It calls the source and target
Ensembl `sequence/region` endpoints plus
`GET /map/human/{from_assembly}/{region}/{to_assembly}`. A successful result
requires source REF verification, one contiguous length-preserving mapping,
strand-aware allele projection, target REF verification and normalization, and
a reverse mapping that recovers the normalized source interval. Mapping or
transport failures are not converted alleles. Symbolic, breakend, MNV, complex
delins, multi-allelic, ambiguous-base, mitochondrial, and structural variants
are out of scope.

For a versioned RefSeq transcript HGVS explicitly rejected as unresolved by
current Ensembl VEP, the adapter may send that scientific variant to NCBI
Variation at
`https://api.ncbi.nlm.nih.gov/variation/v0`: `GET /hgvs/{hgvs}/contextuals`,
`GET /spdi/{spdi}/canonical_representative`, and
`GET /spdi/{canonical_spdi}/hgvs`. It requires one valid contextual allele and a
canonical genomic RefSeq allele, preserves all intermediate representations,
and submits the resulting genomic HGVS to VEP. It does not infer transcript
equivalence from equal c. positions or modify accession versions by string
replacement. Ambiguity, malformed responses, or allele disagreement stops the
workflow.

An Ensembl timeout, malformed response, rate limit, or execution failure does
not trigger the NCBI fallback. It remains an Ensembl service failure, preserving
the service, real endpoint operation, minimized fields disclosed, and retrieval
time. NCBI mapping is attempted only after an explicit unresolved-variant
response.

VEP annotation is not normalization, liftover, independent REF verification, or
classification. Independent REF verification for supported VCF-style genomic
input is a separate `sequence/region` request made before VEP. A timeout,
malformed output, missing dependency, or commit mismatch is a service/capability
failure rather than an absent annotation.

VCEP specification lookup reuses upstream `check_vcep_spec.py`, its registry,
and selected guideline at the same commit. Upstream `classify_variant.py` is not
called because its evidence rules conflict with the local clinical guardrails.
Sequence normalization, a validated corroborating evidence engine, and
literature retrieval will follow the direct-service pattern once their public
contracts are selected.
