#!/usr/bin/env python3
"""Run the pinned VEP client/parser against Ensembl's GRCh37 REST server."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


GRCH37_ENSEMBL_REST_URL = "https://grch37.rest.ensembl.org"


def load_pinned_module(script: Path):
    spec = importlib.util.spec_from_file_location("pinned_vep_annotate", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("The pinned VEP module could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_script", type=Path)
    parser.add_argument("variant")
    args = parser.parse_args()

    module = load_pinned_module(args.upstream_script)
    client = module.VEPClient(base_url=GRCH37_ENSEMBL_REST_URL)
    annotation = module.parse_vep_response(client.annotate(args.variant))
    json.dump(annotation.to_dict(), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
