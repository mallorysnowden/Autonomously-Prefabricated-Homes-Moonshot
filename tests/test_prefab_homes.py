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
    # 0.30*0.65 + 0.18*0.75 + 0.27*0.80 + 0.18*0.95 + 0.07*0.90 + 0.06 transport
    assert m.noak_index(v) == pytest.approx(0.84)


def test_cost_shares_sum_to_one(v):
    assert sum(v[f"cost.share_{c}"] for c in m.COMPONENTS) == pytest.approx(1.0)


def test_price_is_modular_less_discount(v):
    assert m.price_per_sqft(v) == pytest.approx(217 * 0.85 * 0.95)


def test_energy_package_by_hand(v):
    price, cost = m.energy_package(v)
    assert price == pytest.approx(6000 * 2.50 + 13.5 * 800)
    assert cost == pytest.approx(6000 * 1.80 + 13.5 * 550)


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


def test_owner_breakeven_power_price(v):
    price, _ = m.energy_package(v)
    pay = price * v["owner.mortgage_rate"] / (1 - (1 + v["owner.mortgage_rate"]) ** -30)
    vpp = 0.70 * 5 * 70 * 0.70
    assert m.owner_breakeven_power_price(v) == pytest.approx((pay - vpp) / (6 * 1400))


def test_market_cap_binds(v):
    capped = m.run({**v, "market.max_share": 0.0001})  # 100 homes/yr
    assert capped.years[-1].revenue_by_stream["homes"] == pytest.approx(100 * 1800 * m.price_per_sqft(v))
