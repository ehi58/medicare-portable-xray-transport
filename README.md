# How mobile x-ray actually runs: three measurements from Medicare billing data

A reproducible analysis of the public CMS billing file. It asks how Medicare's
portable x-ray suppliers operate: how often a van goes to one patient, how many
patients a shared stop serves, and how concentrated the business is. Every
number comes from public data, and the notebook checks its inputs before it
computes anything.

**Notebook:** [`notebooks/portable-xray-transport.ipynb`](notebooks/portable-xray-transport.ipynb)
(executed, with outputs)

## The question

When an x-ray is taken at a patient's bedside (in a nursing home, an
assisted-living facility or a private home), the supplier bills Medicare for
bringing the equipment. It uses one of two codes: **R0070** when one patient is
seen on the trip, and **R0075** for each patient when several are seen at one
stop. Those two codes are a record of how the work is routed. From them:

1. What share of visits, and of trips, serve a single patient?
2. When a stop is shared, how many patients does it serve? The file never
   states it.
3. How concentrated is the billing across suppliers?

## The data

* **Source.** CMS *Medicare Physician & Other Practitioners: by Provider and
  Service*, calendar year 2024, from the data.cms.gov API.
* **Scope.** 875 rows covering the two transport codes and the set-up code
  Q0092, which is used only as a control. That is 1.1 million transport lines
  from 287 billers.
* **Not included.** No names, addresses or other identifying columns are
  stored. Billers appear only as pseudonyms, and no figure singles one out.
  See [`data/README.md`](data/README.md).

## The method

* **Solo share.** R0070 is one patient per trip, and R0075 is one line per
  patient at a shared stop. The ratio of the two is the solo share of
  *visits*.
* **Stop size, derived from the payment rule.** Medicare pays each shared-stop
  line the single-trip fee divided by the number of patients at the stop
  (capped at six). For any one biller, the ratio of its average single-trip
  allowed amount to its average shared-stop allowed amount is therefore
  exactly its mean number of patients per shared stop (algebra in the
  notebook). The biller's local fee level cancels out. The derivation is
  tested on synthetic stops before it is applied.
* **Concentration.** Lines are summed per biller, ranked, and reported by
  decile. Following the same rule as not naming billers, the largest single
  biller's share is never reported.
* **Controls.** Seven checks run first: row and line totals, a known row,
  CMS's suppression floor, one transport line per patient per day, and the
  biller count. Each finding then has its own: settings sum to the total,
  out-of-bounds ratios are counted and excluded, and deciles sum to 100%. All
  are assertions that stop the notebook if they fail.

## The answer

| | finding |
|---|---|
| **1** | **65%** of patient visits with a transport line are a van sent to one patient. Counted as trips, the share is about **83%** (five in six). The median biller is at 70%. The largest billers run more shared stops, which pulls the national figure down. |
| **2** | A shared stop serves **2.6 patients** on average, weighted by visits (median biller 2.37; 214 of 216 biller-settings inside the bounds the rule allows). Stops near the six-patient cap are under 1% of visits. |
| **3** | The largest tenth of billers (29) bill **61%** of transport visits, and the top ten bill 40%. The median biller billed **977** visits in the year, and half of all billers together hold under 5% of the volume. |

![Solo trips versus shared stops](figures/1-solo-vs-shared.png)
![Implied patients per shared stop](figures/2-stop-size.png)
![Share of transport visits by biller decile](figures/3-concentration.png)

**Limitations.** These travel with every finding and are spelled out in the
notebook:

* Medicare fee-for-service Part B only.
* Billers with fewer than 11 beneficiaries on a code are suppressed by CMS.
* Part A nursing-home stays bundle transport and never appear.
* The setting flag cannot separate a private home from a nursing facility.
* A billing NPI is not a company.
* Stop size is a derivation from allowed amounts, not a count of stops.

## Reproduce it

```
python -m venv .venv && .venv/Scripts/activate      # or: source .venv/bin/activate
pip install -r requirements.txt
python -m cms_transport.fetch --check               # re-pull from data.cms.gov and compare with data/
jupyter nbconvert --to notebook --execute --inplace notebooks/portable-xray-transport.ipynb
pytest                                              # 13 tests: the derivation, the controls, the headline figures
```

## Layout

```
notebooks/portable-xray-transport.ipynb   the analysis, executed
src/cms_transport/fetch.py                API pull, column drop, pseudonyms
src/cms_transport/analysis.py             the three analyses and the controls
src/cms_transport/charts.py               one chart per finding
data/cy2024_transport_rows.csv            the 875-row snapshot (see data/README.md)
figures/                                  the three charts
tests/test_analysis.py                    synthetic and regression tests
```
