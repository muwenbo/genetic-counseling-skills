#!/usr/bin/env python3
"""Validate a 6-column PED file against Pedigree Studio's import rules.

Pedigree Studio (assets/pedigree-chart.html) parses PED as:
  whitespace-split rows, columns = FamilyID IndividualID PaternalID MaternalID Sex Affection
  Sex:       1=male 2=female 0=unknown
  Affection: 1=unaffected 2=affected 0=unknown
Parents named in col 3/4 without their own row are auto-created as unknown-sex.

Usage: python3 validate_ped.py FILE.ped
Exit 0 = valid (warnings allowed), 1 = errors found, 2 = usage error.
"""
import sys

SEX = {"0", "1", "2"}
AFF = {"0", "1", "2"}


def main(argv):
    if len(argv) != 2:
        print("usage: validate_ped.py FILE.ped", file=sys.stderr)
        return 2
    try:
        text = open(argv[1], encoding="utf-8").read()
    except OSError as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2

    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        rows.append((lineno, s.split()))

    errors, warnings = [], []
    ids = {}
    for lineno, cols in rows:
        if len(cols) < 6:
            errors.append(f"line {lineno}: expected >=6 columns, got {len(cols)}: {cols}")
            continue
        fam, iid, pat, mat, sex, aff = cols[:6]
        if iid in ("0", ""):
            errors.append(f"line {lineno}: individual id may not be '0' or empty")
        if iid in ids:
            errors.append(f"line {lineno}: duplicate individual id '{iid}' (first at line {ids[iid]})")
        else:
            ids[iid] = lineno
        if sex not in SEX:
            errors.append(f"line {lineno}: sex '{sex}' invalid (use 0/1/2)")
        if aff not in AFF:
            errors.append(f"line {lineno}: affection '{aff}' invalid (use 0/1/2)")
        if pat == iid or mat == iid:
            errors.append(f"line {lineno}: individual '{iid}' is its own parent")

    # second pass: parent references (need full id set)
    for lineno, cols in rows:
        if len(cols) < 6:
            continue
        _, iid, pat, mat = cols[:4]
        for role, pid in (("paternal", pat), ("maternal", mat)):
            if pid != "0" and pid not in ids:
                warnings.append(
                    f"line {lineno}: {role} id '{pid}' has no row of its own "
                    f"-> auto-created as unknown-sex individual"
                )

    if not rows:
        errors.append("no data rows found")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    n_ind = len(ids)
    print(f"\n{n_ind} individual(s), {len(rows)} row(s), "
          f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
