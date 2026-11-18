import math
from pathlib import Path

import pytest

from tea.inputs import base_values, load_params
from tea import prefab_homes as m

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def v():
    p = {**load_params(ROOT / "inputs/conventions.toml"), **load_params(ROOT / "inputs/prefab_homes.toml")}
    return base_values(p)


def test_noak_cost_index_by_hand(v):
    # conventional: 0.30*0.65 + 0.18*0.75 + 0.27*0.80 + 0.18*0.95 + 0.07*0.90 + 0.06 transport
    assert m.noak_index({**v, "site_system.enabled": 0}) == pytest.approx(0.84)


def test_site_system_overrides_by_hand(v):
    site = 0.58 * 0.40 + 0.42 * 0.10
    expected = 0.30 * 0.65 + 0.18 * 0.75 + 0.27 * 0.80 + 0.18 * (1 - site) + 0.07 * 0.70 + 0.035
    assert m.noak_index(v) == pytest.approx(expected)
    assert m.apply_site_system(v)["time.our_months"] == 3.5


def test_apply_site_system_is_idempotent(v):
    once = m.apply_site_system(v)
    assert m.apply_site_system(once) == once


def test_missed_tolerance_loses_finishing_and_speed_only(v):
    bad = m.apply_site_system({**v, "site_system.joint_tolerance_mm": 6.0})
    assert bad["cost.noak_reduction_final"] == v["cost.noak_reduction_final"]
    assert bad["time.our_months"] == v["time.our_months"]
    assert bad["cost.transport_set"] == v["site_system.set_cost"]


def test_financing_scales_with_build_time(v):
    assert m.financing_share(v) == pytest.approx(0.015 * 3.5 / 8.8)


def test_cost_shares_sum_to_one(v):
    assert sum(v[f"cost.share_{c}"] for c in m.COMPONENTS) == pytest.approx(1.0)


def test_price_is_modular_less_discount(v):
    assert m.price_per_sqft(v) == pytest.approx(217 * 0.85 * 0.95)


def test_package_price_by_hand(v):
    assert m.package_price_cost(v, "solar") == pytest.approx((6000 * 2.50, 6000 * 1.80))
    assert m.package_price_cost(v, "solar + battery") == pytest.approx(
        (6000 * 2.50 + 13.5 * 800, 6000 * 1.80 + 13.5 * 550))


def test_cost_index_reaches_noak(v):
    assert m.cost_index(v, v["learning.noak_experience"]) == pytest.approx(m.noak_index(v))
    assert m.cost_index(v, v["learning.first_year_experience"]) > m.noak_index(v)


def test_rd_years_have_no_revenue(v):
    r = m.run(v)
    assert len(r.years) == int(v["finance.horizon"])
    assert all(y.revenue == 0 for y in r.years[: int(v["company.rd_years"])])


def test_cash_is_ebit_less_capex(v):
    r = m.run(v)
    total = sum(y.ebit - y.capex for y in r.years)
    assert r.years[-1].cumulative_cash == pytest.approx(total)


def test_first_commercial_year_units(v):
    # one new factory at first-year utilization: 250 * 0.40 = 100 homes
    r = m.run(v)
    y = r.years[int(v["company.rd_years"])]
    assert y.revenue_by_stream["homes"] == pytest.approx(100 * 1800 * m.price_per_sqft(v))


def test_adu_uses_less_line_time(v):
    v2 = {**v, "adu.enabled": 1}
    y = m.run(v2).years[int(v["company.rd_years"])]
    adus = 100 * v["adu.share_of_units"] / v["adu.slot_fraction"]
    assert y.revenue_by_stream["adus"] == pytest.approx(adus * 600 * 290)


def test_add_ons_off_means_homes_only(v):
    off = {**v, "energy.enabled": 0, "vpp.enabled": 0, "service.enabled": 0}
    s = m.run(off).years[-1].revenue_by_stream
    assert s["energy"] == s["vpp"] == s["service"] == 0


def test_owner_value_net_metering_by_hand(v):
    # New England: export = retail, so the battery only adds VPP income
    val = m.owner_value(v, "ne")
    solar = 6 * 1150 * 0.30
    assert val["solar"] == pytest.approx(solar)
    assert val["solar + battery"] - val["solar"] == pytest.approx(0.70 * 5 * 250 * 0.70)


def test_owner_value_net_billing_by_hand(v):
    # California: battery shifts exports, capped by battery throughput
    solar = 6 * 1600
    shifted = min(solar * 0.40, 13.5 * 300)
    shift_value = shifted * (0.32 * 0.90 - 0.05)
    vpp = 0.70 * 5 * 70 * 0.70
    val = m.owner_value(v, "ca")
    assert val["solar + battery"] - val["solar"] == pytest.approx(shift_value + vpp)


def test_package_choice_follows_owner_savings(v):
    for r in m.REGIONS:
        net = m.owner_net(v, r)
        pick = m.chosen_package(v, r)
        assert net[pick] == max(net.values())
        assert pick == "none" or net[pick] > 0
    assert m.chosen_package({**v, "energy.enabled": 0}, "ca") == "none"


def test_market_cap_binds(v):
    capped = m.run({**v, "market.max_share": 0.0001})  # 100 homes/yr
    assert capped.years[-1].revenue_by_stream["homes"] == pytest.approx(100 * 1800 * m.price_per_sqft(v))
