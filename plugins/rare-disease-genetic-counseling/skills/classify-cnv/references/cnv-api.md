# CNV Classification API

Base URL: `https://cnvclassifier.viknox.com/`

- Health: `GET /health`
- Classify: `POST /api/v1/classify`
- Content type: `application/json`
- Limit: 120 requests/minute/IP; batch variants in one request.

Coordinates are 1-based and inclusive. The engine scores on GRCh38. The plugin
requires an explicit `genome_build` even though the service accepts hg38 as a
default.

## Request

```json
{
  "variants": [
    {
      "chrom": "chr22",
      "start": 19000000,
      "end": 21500000,
      "cnv_type": "loss",
      "genome_build": "hg38",
      "hpo_terms": ["HP:0001250"],
      "inheritance": "de_novo_confirmed",
      "phenotype_consistency": "consistent",
      "reported_cases": [
        {"inheritance": "de_novo_confirmed", "phenotype": "specific"}
      ],
      "reported_segregation": {
        "affected_with_variant": 3,
        "affected_without_variant": 0
      },
      "case_control_studies": [
        {"significant": true, "phenotype_specific": true}
      ]
    }
  ]
}
```

Required variant fields: `chrom`, `start`, `end`, `cnv_type`, and—by plugin
policy—`genome_build`.

Accepted chromosomes are 1-22, X, and Y with optional `chr`. `cnv_type` is
`loss` or `gain`. `genome_build` is `hg38` or `hg19`.

Only send optional evidence that has been reviewed. Keep reported cases and
reported segregation separate from proband/family evidence.

## Response

```json
{
  "results": [
    {
      "classification": "Pathogenic",
      "total_points": 1.0,
      "section_scores": {"1": 0.0, "2": 1.0, "3": 0.0, "4": 0.0, "5": 0.0},
      "evidence": [
        {
          "category_id": "2A",
          "points": 1.0,
          "suggested_range": null,
          "reason": "..."
        }
      ],
      "pending_evidence": [],
      "liftover": null
    }
  ]
}
```

Results align with inputs by array position. Preserve all fields.

For hg19, a refused lift returns `classification: null`,
`liftover.status: "failed"`, and a reason. This is a failed classification, not
VUS. Never score the original hg19 coordinates as though they were hg38.

Coordinate-only mid-size CNVs commonly remain uncertain. Do not invent clinical
evidence to change a tier.
