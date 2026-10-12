# data/

`cy2024_transport_rows.csv`: 875 rows from the CMS public file *Medicare
Physician & Other Practitioners: by Provider and Service*, calendar year 2024
(data.cms.gov dataset `92396110-2aed-4d63-a6a2-5d6207d46a29`), filtered to
HCPCS R0070, R0075 and Q0092.

The file was first pulled on 2026-09-15 and re-pulled on 2026-10-12. The two
pulls are identical (`repull-check-2026-10-12.txt`). `python -m cms_transport.fetch --check` repeats that
comparison against the live API.

| column | source column | meaning |
|---|---|---|
| `biller` | `Rndrng_NPI` | pseudonym for the rendering NPI (see below) |
| `entity_code` | `Rndrng_Prvdr_Ent_Cd` | `O` organisation, `I` individual |
| `provider_type` | `Rndrng_Prvdr_Type` | Medicare enrolment type |
| `hcpcs` | `HCPCS_Cd` | R0070, R0075 or Q0092 |
| `setting` | `Place_Of_Srvc` | `F` facility, `O` non-facility |
| `beneficiaries` | `Tot_Benes` | distinct beneficiaries |
| `services` | `Tot_Srvcs` | billed lines |
| `beneficiary_days` | `Tot_Bene_Day_Srvcs` | distinct beneficiary-days |
| `avg_allowed` | `Avg_Mdcr_Alowd_Amt` | average Medicare allowed amount per line |

**Dropped at download.** Every name, street address, city, ZIP, state, FIPS
and RUCA column. They are never written to disk.

**Pseudonyms.** NPIs are numbered in the order of their SHA-256 hash, so a
pseudonym carries no information about size or place. The source file is
public, so this is a presentation choice: no table or chart can single out a
company. It is not a privacy control.

**Suppression.** CMS omits any biller-code-setting cell with fewer than 11
beneficiaries. The smallest value in this file is 11.
