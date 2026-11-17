"""Automated factories for electrified prefab homes: TEA on the standard framework.

A network of robotic microfactories builds all-electric homes (optionally with
factory-installed solar and batteries) and earns recurring revenue from the
homes it delivers.

House cost per sq ft = site-built construction cost x sum_c(share_c x multiplier_c)
                       + transport and set
Each component's multiplier falls from FOAK to NOAK with cumulative units built
(Wright's law) and stays at NOAK. Price is the conventional-modular price less a
discount, so the product must beat conventional prefab on price.

Revenue streams: homes, ADUs (optional), energy package, VPP aggregation,
home-systems service, panels sold to other builders (optional).
Cash = operating profit - factory capex. Operating profit is before depreciation.
"""
from __future__ import annotations

from .finance import crf, irr, npv
from .framework.learning import cost_multiplier
from .framework.result import FunctionalUnit, KillMetric, StandardResult, YearRow
from .framework.uncertainty import breakeven

COMPONENTS = ("structure", "mep", "finishes", "site", "final")


def _noak(v, c: str) -> float:
    return 1 - v[f"cost.noak_reduction_{c}"]


def cost_index(v, experience: float) -> float:
    """House cost per sq ft as a multiple of site-built construction cost (incl. transport and set)."""
    mult = sum(v[f"cost.share_{c}"] * cost_multiplier(experience, v["learning.noak_experience"], _noak(v, c),
                                                     v[f"learning.rate_{c}"]) for c in COMPONENTS)
    return mult + v["cost.transport_set"]


def noak_index(v) -> float:
    return sum(v[f"cost.share_{c}"] * _noak(v, c) for c in COMPONENTS) + v["cost.transport_set"]


def price_per_sqft(v) -> float:
    return v["bench.site_built_price_per_sqft"] * (1 - v["bench.modular_discount"]) * (1 - v["price.discount_vs_modular"])


def energy_package(v) -> tuple[float, float]:
    """(price, cost) of the factory-installed solar + battery package per home."""
    kw, kwh = v["energy.solar_kw"], v["energy.battery_kwh"]
    price = kw * 1000 * v["energy.solar_price_per_w"] + kwh * v["energy.battery_price_per_kwh"]
    cost = kw * 1000 * v["energy.solar_cost_per_w"] + kwh * v["energy.battery_cost_per_kwh"]
    return price, cost


def factory_overhead_per_sqft(v) -> float:
    """Fixed factory cost per sq ft at full utilization, with capex annualized at the company rate."""
    sqft = v["factory.capacity"] * v["factory.utilization"] * v["home.sqft"]
    annual = v["factory.fixed_opex"] + v["factory.capex"] * crf(v["finance.company_discount_rate"], v["factory.life"])
    return annual / sqft


def owner_energy_bill(v, with_package: bool) -> float:
    bill = v["owner.energy_bill_mixed_fuel"] * (1 + v["owner.all_electric_bill_change"])
    if not with_package:
        return bill
    solar = v["energy.solar_kw"] * v["owner.solar_kwh_per_kw"] * v["owner.electricity_price"]
    vpp = (v["vpp.enabled"] * v["vpp.enrollment"] * v["vpp.kw_per_home"] * v["vpp.payment_per_kw_year"]
           * (1 - v["vpp.our_share"]))
    return max(bill - solar, 0.0) - vpp


def owner_breakeven_power_price(v) -> float:
    """Electricity price at which the solar + battery package pays for itself inside a 30-year mortgage."""
    pkg_price, _ = energy_package(v)
    vpp = (v["vpp.enabled"] * v["vpp.enrollment"] * v["vpp.kw_per_home"] * v["vpp.payment_per_kw_year"]
           * (1 - v["vpp.our_share"]))
    return (pkg_price * crf(v["owner.mortgage_rate"], 30) - vpp) / (v["energy.solar_kw"] * v["owner.solar_kwh_per_kw"])


def functional_units(v) -> list[FunctionalUnit]:
    site_cost = v["bench.site_built_cost_per_sqft"]
    p_ours = price_per_sqft(v)
    p_mod = v["bench.site_built_price_per_sqft"] * (1 - v["bench.modular_discount"])
    p_site = v["bench.site_built_price_per_sqft"]
    full_cost = (site_cost * noak_index(v) + factory_overhead_per_sqft(v)
                 - v["owner.gas_line_avoided"] / v["home.sqft"]) / (1 - v["company.selling_cost"] - v["company.warranty"] - v["company.ga_share"])
    price = FunctionalUnit(
        "Installed home, excluding land", "$/sq ft",
        {"Ours at NOAK price": p_ours, "Conventional modular": p_mod, "Site-built": p_site,
         "Manufactured (HUD code, reference)": v["bench.manufactured_price_per_sqft"],
         "Ours priced at NOAK full cost": full_cost},
        "Full cost includes factory overhead, capex, selling, warranty and G&A at full utilization.",
    )
    months = FunctionalUnit(
        "Time to occupancy", "months from permit",
        {"Ours": v["time.our_months"], "Conventional modular": v["bench.site_built_months"] - v["bench.modular_months_saved"],
         "Site-built": v["bench.site_built_months"]},
    )
    sqft = v["home.sqft"]
    pay = crf(v["owner.mortgage_rate"], 30)
    pkg_price, _ = energy_package(v)
    owner = FunctionalUnit(
        "Owner's annual cost (home + energy)", "$/yr",
        {"Ours, all-electric with solar + battery": (p_ours * sqft + pkg_price) * pay + owner_energy_bill(v, True),
         "Ours, all-electric, no package": p_ours * sqft * pay + owner_energy_bill(v, False),
         "Conventional modular, mixed fuel": p_mod * sqft * pay + v["owner.energy_bill_mixed_fuel"],
         "Site-built, mixed fuel": p_site * sqft * pay + v["owner.energy_bill_mixed_fuel"]},
        "Home price financed over 30 years at the mortgage rate; excludes land, taxes and insurance.",
    )
    return [price, months, owner]


def run(v) -> StandardResult:
    horizon = int(v["finance.horizon"])
    rd = int(round(v["company.rd_years"]))
    sched = v["factory.schedule"]
    rate = v["finance.company_discount_rate"]
    site_cost = v["bench.site_built_cost_per_sqft"]
    p_sqft = price_per_sqft(v)
    pkg_price, pkg_cost = energy_package(v)
    cap = v["market.single_family_completions"] * v["market.max_share"]  # factory slots (home-equivalents)
    adu_share = v["adu.share_of_units"] * v["adu.enabled"]

    experience = v["learning.first_year_experience"]
    prev_factories = 0
    cum_units = 0.0
    cum_battery_homes = 0.0
    cumulative = 0.0
    learning_investment = 0.0
    noak_year = None
    rows: list[YearRow] = []

    for t in range(1, horizon + 1):
        k = t - rd
        streams = {s: 0.0 for s in ("homes", "adus", "energy", "vpp", "service", "panels")}
        capex = 0.0
        if k >= 1:
            phase = "commercial"
            factories = sched[min(k, len(sched)) - 1]
            new = max(factories - prev_factories, 0)
            capex = new * v["factory.capex"]
            slots = v["factory.capacity"] * ((factories - new) * v["factory.utilization"] + new * v["factory.first_year_utilization"])
            slots = min(slots, cap)
            prev_factories = factories
        else:
            phase, factories, slots = "R&D", 0, 0.0

        houses = slots * (1 - adu_share)
        adus = slots * adu_share / v["adu.slot_fraction"]
        units = houses + adus
        idx = cost_index(v, experience)
        house_cost_sqft = site_cost * idx
        house_cogs = houses * (v["home.sqft"] * house_cost_sqft - v["owner.gas_line_avoided"])
        adu_cogs = adus * v["adu.sqft"] * house_cost_sqft * v["adu.cost_premium"]
        learning_investment += (houses * v["home.sqft"] + adus * v["adu.sqft"] * v["adu.cost_premium"]) * site_cost * (idx - noak_index(v))

        energy_homes = houses * v["energy.take_rate"] * v["energy.enabled"]
        streams["homes"] = houses * v["home.sqft"] * p_sqft
        streams["adus"] = adus * v["adu.sqft"] * v["adu.price_per_sqft"]
        streams["energy"] = energy_homes * pkg_price
        streams["vpp"] = (cum_battery_homes * v["vpp.enabled"] * v["vpp.enrollment"] * v["vpp.kw_per_home"]
                          * v["vpp.payment_per_kw_year"] * v["vpp.our_share"])
        streams["service"] = cum_units * v["service.enabled"] * v["service.attach"] * v["service.fee_per_year"]
        streams["panels"] = factories * v["panels.enabled"] * v["panels.revenue_per_factory"]

        product_rev = streams["homes"] + streams["adus"] + streams["energy"]
        cos = (house_cogs + adu_cogs + energy_homes * pkg_cost
               + product_rev * (v["company.selling_cost"] + v["company.warranty"])
               + streams["service"] * (1 - v["service.margin"])
               + streams["panels"] * (1 - v["panels.margin"])
               + factories * v["factory.fixed_opex"])
        revenue = sum(streams.values())
        gross = revenue - cos
        opex = v["company.rd_opex"] if phase == "R&D" else v["company.corporate_opex"] + revenue * v["company.ga_share"]
        ebit = gross - opex
        cumulative += ebit - capex
        rows.append(YearRow(t, phase, revenue, cos, gross, opex, ebit, cumulative, idx, streams, capex))

        experience += slots  # home-equivalents of line time
        cum_units += units
        cum_battery_homes += energy_homes
        if noak_year is None and experience >= v["learning.noak_experience"]:
            noak_year = t

    final_homes = houses + adus
    cash = [r.ebit - r.capex for r in rows]
    went_negative, breakeven_year = False, None
    for r in rows:
        if r.cumulative_cash < 0:
            went_negative = True
        elif went_negative and breakeven_year is None:
            breakeven_year = r.year

    fus = functional_units(v)
    price_fu, months_fu = fus[0].options, fus[1].options
    noak_idx = noak_index(v)
    full_cost = price_fu["Ours priced at NOAK full cost"]
    margin = 1 - full_cost / price_fu["Ours at NOAK price"]
    big = v["scale.big_enough_revenue"]
    kills = [
        KillMetric("NOAK full cost vs conventional-modular price", full_cost / price_fu["Conventional modular"], 1.0,
                   "x (<=1 to win)", full_cost <= price_fu["Conventional modular"],
                   "Your requirement: cost-competitive with conventionally built prefab"),
        KillMetric("Time to occupancy vs conventional modular", months_fu["Ours"] / months_fu["Conventional modular"], 1.0,
                   "x (<1 to win)", months_fu["Ours"] < months_fu["Conventional modular"],
                   "Your requirement: shorter build and delivery"),
        KillMetric("NOAK construction cost vs site-built (incl. transport)", noak_idx, 0.85, "x (<=0.85 to win)",
                   noak_idx <= 0.85, "Must beat modular's typical ~15% advantage at the cost level"),
        KillMetric("NOAK margin on homes after overhead, capex, selling, warranty and G&A", margin, 0.10, "fraction",
                   margin >= 0.10, "10% threshold is a judgment (site-built builders averaged 11% in 2024)"),
        KillMetric("Revenue at full scale vs big-enough line", rows[-1].revenue / big, 1.0, "x", rows[-1].revenue >= big),
    ]
    foak = {c: cost_multiplier(v["learning.first_year_experience"], v["learning.noak_experience"], _noak(v, c),
                               v[f"learning.rate_{c}"]) for c in COMPONENTS}
    return StandardResult(
        project="Automated factories for electrified prefab homes",
        years=rows,
        npv=npv(rate, cash),
        irr=irr(cash),
        peak_cash_need=-min(0.0, min(r.cumulative_cash for r in rows)),
        breakeven_year=breakeven_year,
        full_scale_revenue=rows[-1].revenue,
        functional_units=fus,
        learning={c: (foak[c], _noak(v, c)) for c in COMPONENTS},
        noak_year=noak_year,
        learning_investment=learning_investment,
        kill_metrics=kills,
        notes=[
            f"Market check: year-{horizon} output is {final_homes:,.0f} homes/yr, vs ~30,000 modular + panelized homes built in the US in 2025 (3% of single-family).",
            f"Owner check: the solar + battery package pays for itself in the mortgage only above ${owner_breakeven_power_price(v):.3f}/kWh (base ${v['owner.electricity_price']:.3f}); all solar output is valued at the retail rate, which flatters it under net billing.",
            "Cost multipliers are relative to the site-built construction cost (NAHB 2024: $162/sq ft); 'Cost vs incumbent' in the cash flow includes transport and set.",
            "Operating profit is before depreciation; factory capex is a separate cash outflow. No taxes, working capital or terminal value.",
            "Federal 45L and 25D credits ended in 2026, so no subsidies are counted.",
        ],
    )


def breakevens(v) -> list[dict]:
    npv_of = lambda x: run(x).npv  # noqa: E731
    out = []
    for key, lo, hi, label in [
        ("factory.capex", 0, 300_000_000, "Factory capex for NPV = 0"),
        ("factory.utilization", 0.05, 1.0, "Factory utilization for NPV = 0"),
        ("price.discount_vs_modular", -0.5, 0.5, "Price discount vs conventional modular for NPV = 0"),
        ("cost.noak_reduction_mep", 0.0, 0.95, "MEP cost reduction for NPV = 0"),
    ]:
        out.append({"question": label, "input": key, "answer": breakeven(v, key, npv_of, 0.0, lo, hi), "base": v[key]})
    return out


def scenarios(v) -> list[tuple[str, dict]]:
    """Revenue add-ons, each switched on or off against the base case."""
    core = {"energy.enabled": 0, "vpp.enabled": 0, "service.enabled": 0, "panels.enabled": 0, "adu.enabled": 0}
    return [
        ("Homes only (no add-ons)", core),
        ("+ Energy package", {**core, "energy.enabled": 1}),
        ("+ Energy package + VPP", {**core, "energy.enabled": 1, "vpp.enabled": 1}),
        ("Base case (energy + VPP + service)", {}),
        ("Base + panels for other builders", {"panels.enabled": 1}),
        ("Base + ADU line", {"adu.enabled": 1}),
        ("All add-ons", {"panels.enabled": 1, "adu.enabled": 1}),
    ]
