"""Pull the CY2024 portable x-ray transport rows from data.cms.gov.

The source is the public "Medicare Physician & Other Practitioners - by
Provider and Service" file for calendar year 2024. Three HCPCS codes are
pulled:

    R0070  transport of portable x-ray equipment, one patient seen
    R0075  transport of portable x-ray equipment, more than one patient seen
    Q0092  set-up of portable x-ray equipment (one per patient)

What is kept, and what is not:

* Name, address, city, ZIP, state and RUCA columns are never written to disk.
  The analyses are national and need only to group rows by biller.
* The rendering NPI is replaced by a pseudonym (``B001``...). The pseudonym
  only stops an identifier appearing in any table or chart; anyone can re-pull
  the public file, so it is a presentation choice, not a privacy control.

Usage::

    python -m cms_transport.fetch            # writes data/cy2024_transport_rows.csv
    python -m cms_transport.fetch --check    # pull and compare with the committed file
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

DATASET_ID = "92396110-2aed-4d63-a6a2-5d6207d46a29"
API = f"https://data.cms.gov/data-api/v1/dataset/{DATASET_ID}/data"
CODES = ("R0070", "R0075", "Q0092")
PAGE = 5000

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "cy2024_transport_rows.csv"

# Source column -> snapshot column. Anything not listed is dropped on read.
KEEP = {
    "Rndrng_NPI": "npi",  # replaced by `biller` before writing
    "Rndrng_Prvdr_Ent_Cd": "entity_code",
    "Rndrng_Prvdr_Type": "provider_type",
    "HCPCS_Cd": "hcpcs",
    "Place_Of_Srvc": "setting",
    "Tot_Benes": "beneficiaries",
    "Tot_Srvcs": "services",
    "Tot_Bene_Day_Srvcs": "beneficiary_days",
    "Avg_Mdcr_Alowd_Amt": "avg_allowed",
}
NUMERIC = ["beneficiaries", "services", "beneficiary_days", "avg_allowed"]


def _pull_code(code: str, session: requests.Session) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        r = session.get(
            API,
            params={"filter[HCPCS_Cd]": code, "size": PAGE, "offset": offset},
            timeout=120,
        )
        r.raise_for_status()
        page = r.json()
        rows.extend({k: rec.get(k) for k in KEEP} for rec in page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def pseudonymise(npis: pd.Series) -> pd.Series:
    """Map each NPI to a stable pseudonym, ordered by a hash of the NPI.

    The order carries no information about size or location.
    """
    unique = sorted(set(npis), key=lambda n: hashlib.sha256(n.encode()).hexdigest())
    width = max(3, len(str(len(unique))))
    mapping = {n: f"B{i + 1:0{width}d}" for i, n in enumerate(unique)}
    return npis.map(mapping)


def pull() -> pd.DataFrame:
    with requests.Session() as s:
        records = [row for code in CODES for row in _pull_code(code, s)]
    df = pd.DataFrame.from_records(records).rename(columns=KEEP)
    df["biller"] = pseudonymise(df["npi"].astype(str))
    df = df.drop(columns=["npi"])
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col])
    cols = ["biller"] + [c for c in KEEP.values() if c != "npi"]
    return df[cols].sort_values(["hcpcs", "biller", "setting"]).reset_index(drop=True)


def load_snapshot() -> pd.DataFrame:
    return pd.read_csv(SNAPSHOT, dtype={"biller": str, "entity_code": str, "setting": str})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--check", action="store_true", help="compare a fresh pull with the committed snapshot")
    args = p.parse_args(argv)

    fresh = pull()
    if args.check:
        old = load_snapshot()
        same = fresh.reset_index(drop=True).equals(old.reset_index(drop=True))
        print(f"fresh pull {len(fresh)} rows; snapshot {len(old)} rows; identical: {same}")
        return 0 if same else 1

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(SNAPSHOT, index=False)
    print(f"wrote {len(fresh)} rows to {SNAPSHOT.relative_to(ROOT)} ({date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
