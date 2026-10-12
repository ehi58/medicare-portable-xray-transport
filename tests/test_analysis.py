import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cms_transport import analysis as A  # noqa: E402
from cms_transport.fetch import load_snapshot, pseudonymise  # noqa: E402


def price_stops(fee: float, stops: list[int]) -> float:
    """Average R0075 allowed amount for a biller whose shared stops are `stops`."""
    lines = [fee / min(n, 6) for n in stops for _ in range(n)]
    return sum(lines) / len(lines)


@pytest.mark.parametrize(
    "stops",
    [[2], [2, 2, 2], [2, 3], [3, 3, 4, 2, 5], [6, 2], list(range(2, 7))],
)
def test_ratio_of_averages_recovers_mean_stop_size(stops):
    fee = 87.5
    assert A.implied_stop_size(fee, price_stops(fee, stops)) == pytest.approx(np.mean(stops))


def test_stops_above_six_make_the_estimate_a_floor():
    fee, stops = 100.0, [2, 9]
    assert A.implied_stop_size(fee, price_stops(fee, stops)) < np.mean(stops)


def test_ratio_band_matches_the_rule():
    fee = 100.0
    assert price_stops(fee, [2]) / fee == pytest.approx(A.RATIO_HIGH)
    assert price_stops(fee, [6]) / fee == pytest.approx(A.RATIO_LOW)


def test_gini_bounds():
    assert A.gini(np.ones(10)) == pytest.approx(0.0)
    assert A.gini(np.array([0] * 9 + [1])) == pytest.approx(0.9)


def test_pseudonyms_are_stable_and_unique():
    npis = pd.Series(["1234567890", "1111111111", "1234567890", "2222222222"])
    a, b = pseudonymise(npis), pseudonymise(npis.iloc[::-1]).iloc[::-1]
    assert list(a) == list(b)
    assert a.nunique() == 3
    assert not a.str.contains(r"\d{10}").any()


@pytest.fixture(scope="module")
def df():
    return load_snapshot()


def test_snapshot_has_no_identifying_columns(df):
    assert set(df.columns) == {
        "biller", "entity_code", "provider_type", "hcpcs", "setting",
        "beneficiaries", "services", "beneficiary_days", "avg_allowed",
    }


def test_controls_pass(df):
    failed = [c for c in A.controls(df) if not c.passed]
    assert not failed, failed


def test_headline_figures(df):
    s = A.solo_share(df)
    assert (s["solo_lines"], s["shared_lines"]) == (723_699, 385_487)
    z = A.stop_sizes(df)
    assert (z["n_pairs"], z["n_used"]) == (216, 214)
    assert z["weighted"] == pytest.approx(2.557, abs=1e-3)
    c = A.concentration(df)
    assert c["billers"] == 287
    assert c["lines"] == s["solo_lines"] + s["shared_lines"]
    assert c["deciles"].share_of_lines.sum() == pytest.approx(1.0)
    assert c["deciles"].billers.sum() == 287
