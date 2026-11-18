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


def joints_ok(v) -> bool:
    return v["site_system.joint_tolerance_mm"] <= v["site_system.tolerance_needed_mm"]


def apply_site_system(v) -> dict:
    """Inputs with the site system's overrides applied (idempotent).

    If the assembled joints miss the tolerance needed for no finishing rework, the
    finishing savings and the faster schedule are lost; the foundation and set savings stay.
    """
    if not v.get("site_system.enabled"):
        return v
    out = dict(v)
    fs = v["site_system.foundation_share"]
    out["cost.noak_reduction_site"] = fs * v["site_system.foundation_reduction"] + (1 - fs) * v["site_system.sitework_reduction"]
    out["cost.transport_set"] = v["site_system.set_cost"]
    out["learning.rate_site"] = v["site_system.learning_rate"]
    if joints_ok(v):
        out["cost.noak_reduction_final"] = v["site_system.final_reduction"]
        out["learning.rate_final"] = v["site_system.learning_rate"]
        out["time.our_months"] = v["site_system.our_months"]
    out["site_system.enabled"] = 0  # already applied
    out["site_system.applied"] = 1
    return out


def _noak(v, c: str) -> float:
    return 1 - v[f"cost.noak_reduction_{c}"]


def cost_index(v, experience: float) -> float:
    """House cost per sq ft as a multiple of site-built construction cost (incl. transport and set)."""
    v = apply_site_system(v)
    mult = sum(v[f"cost.share_{c}"] * cost_multiplier(experience, v["learning.noak_experience"], _noak(v, c),
                                                     v[f"learning.rate_{c}"]) for c in COMPONENTS)
    return mult + v["cost.transport_set"]


def noak_index(v) -> float:
    v = apply_site_system(v)
    return sum(v[f"cost.share_{c}"] * _noak(v, c) for c in COMPONENTS) + v["cost.transport_set"]


def price_per_sqft(v) -> float:
    return v["bench.site_built_price_per_sqft"] * (1 - v["bench.modular_discount"]) * (1 - v["price.discount_vs_modular"])


REGIONS = {
    "ca": "CA / HI (high rates, net billing)",
    "ne": "New England / NY (high rates, net metering, battery programs)",
    "se": "Southeast (full net metering)",
    "tx": "Texas-style buyback",
    "mw": "Mountain / Midwest (cheap power, net billing)",
}
PACKAGES = ("none", "solar", "solar + battery")


def region_shares(v) -> dict[str, float]:
    total = sum(v[f"region_{r}.share"] for r in REGIONS)
    return {r: v[f"region_{r}.share"] / total for r in REGIONS}


def package_price_cost(v, package: str) -> tuple[float, float]:
    """(price to buyer, our installed cost) of an energy package per home."""
    if package == "none":
        return 0.0, 0.0
    w = v["energy.solar_kw"] * 1000
    price, cost = w * v["energy.solar_price_per_w"], w * v["energy.solar_cost_per_w"]
    if package == "solar + battery":
        price += v["energy.battery_kwh"] * v["energy.battery_price_per_kwh"]
        cost += v["energy.battery_kwh"] * v["energy.battery_cost_per_kwh"]
    return price, cost


def owner_value(v, r: str) -> dict[str, float]:
    """Owner's yearly bill savings and VPP income for each package in region r (before paying for it)."""
    retail, export = v[f"region_{r}.retail"], v[f"region_{r}.export"]
    solar = v["energy.solar_kw"] * v[f"region_{r}.solar_yield"]
    self_use = v["energy.self_use"]
    solar_value = solar * (self_use * retail + (1 - self_use) * export)
    shifted = min(solar * (1 - self_use), v["energy.battery_kwh"] * v["energy.battery_cycles_per_year"])
    shift_value = shifted * max(retail * v["energy.round_trip"] - export, 0.0)
    vpp = (v["vpp.enabled"] * v["vpp.enrollment"] * v["vpp.kw_per_home"] * v[f"region_{r}.vpp_payment"]
           * (1 - v["vpp.our_share"]))
    return {"none": 0.0, "solar": solar_value, "solar + battery": solar_value + shift_value + vpp}


def owner_net(v, r: str) -> dict[str, float]:
    """Owner's yearly net gain from each package, with its price financed in a 30-year mortgage."""
    pay = crf(v["owner.mortgage_rate"], 30)
    val = owner_value(v, r)
    return {p: val[p] - package_price_cost(v, p)[0] * pay for p in PACKAGES}


def chosen_package(v, r: str) -> str:
    """The package we offer in region r: whichever saves the owner most, or none."""
    if not v["energy.enabled"]:
        return "none"
    net = owner_net(v, r)
    best = max(PACKAGES, key=net.get)
    return best if net[best] > 0 else "none"


def financing_share(v) -> float:
    """Our construction financing as a fraction of price, scaled to our build time."""
    v = apply_site_system(v)
    return v["company.construction_financing"] * v["time.our_months"] / v["bench.site_built_months"]


def factory_overhead_per_sqft(v) -> float:
    """Fixed factory cost per sq ft at full utilization, with capex annualized at the company rate."""
    sqft = v["factory.capacity"] * v["factory.utilization"] * v["home.sqft"]
    annual = v["factory.fixed_opex"] + v["factory.capex"] * crf(v["finance.company_discount_rate"], v["factory.life"])
    return annual / sqft


def noak_full_cost(v, selling_cost: float) -> float:
    """$/sq ft at which a home just covers NOAK cost, factory overhead and capex, selling, warranty, G&A and financing."""
    v = apply_site_system(v)
    direct = v["bench.site_built_cost_per_sqft"] * noak_index(v) + factory_overhead_per_sqft(v) - v["owner.gas_line_avoided"] / v["home.sqft"]
    return direct / (1 - selling_cost - v["company.warranty"] - v["company.ga_share"] - financing_share(v))


def functional_units(v) -> list[FunctionalUnit]:
    v = apply_site_system(v)
    site_cost = v["bench.site_built_cost_per_sqft"]
    p_ours = price_per_sqft(v)
    p_mod = v["bench.site_built_price_per_sqft"] * (1 - v["bench.modular_discount"])
    p_site = v["bench.site_built_price_per_sqft"]
    full_cost = noak_full_cost(v, v["company.selling_cost"])
    price = FunctionalUnit(
        "Installed home, excluding land", "$/sq ft",
        {"Ours at NOAK price": p_ours, "Ours to build-to-rent buyers": p_ours * (1 - v["btr.price_discount"]),
         "Conventional modular": p_mod, "Site-built": p_site,
         "Manufactured (HUD code, reference)": v["bench.manufactured_price_per_sqft"],
         "Ours priced at NOAK full cost": full_cost},
        "Full cost includes factory overhead, capex, selling, warranty, G&A and construction financing at full utilization.",
    )
    months = FunctionalUnit(
        "Time to occupancy", "months from permit",
        {"Ours": v["time.our_months"], "Conventional modular": v["bench.site_built_months"] - v["bench.modular_months_saved"],
         "Site-built": v["bench.site_built_months"]},
    )
    wait = FunctionalUnit(
        "Buyer's cost of waiting for the home", "$ per home",
        {k: m * v["owner.monthly_carrying_cost"] for k, m in months.options.items()},
        "Months from permit to occupancy x rent or a second housing payment.",
    )
    sqft = v["home.sqft"]
    pay = crf(v["owner.mortgage_rate"], 30)
    shares = region_shares(v)
    gain = sum(shares[r] * owner_net(v, r)[chosen_package(v, r)] for r in REGIONS)
    electric = v["owner.energy_bill_mixed_fuel"] * (1 + v["owner.all_electric_bill_change"])
    owner = FunctionalUnit(
        "Owner's annual cost (home + energy)", "$/yr",
        {"Ours, all-electric with the regional package (sales-weighted)": p_ours * sqft * pay + electric - gain,
         "Ours, all-electric, no package": p_ours * sqft * pay + electric,
         "Conventional modular, mixed fuel": p_mod * sqft * pay + v["owner.energy_bill_mixed_fuel"],
         "Site-built, mixed fuel": p_site * sqft * pay + v["owner.energy_bill_mixed_fuel"]},
        "Home price and package financed over 30 years at the mortgage rate; excludes land, taxes and insurance.",
    )
    return [price, months, wait, owner]


def region_table(v) -> tuple[str, list[str], list[list[str]]]:
    shares = region_shares(v)
    rows = []
    for r, name in REGIONS.items():
        net = owner_net(v, r)
        rows.append([name, f"{shares[r]:.0%}", f"${v[f'region_{r}.retail']:.3f}", f"${v[f'region_{r}.export']:.3f}",
                     f"${v[f'region_{r}.vpp_payment']:,.0f}", f"${net['solar']:,.0f}", f"${net['solar + battery']:,.0f}",
                     chosen_package(v, r)])
    return ("Energy package by region: owner's net gain per year, financed in the mortgage",
            ["Region", "Sales", "Retail $/kWh", "Export $/kWh", "VPP $/kW-yr", "Solar only", "Solar + battery", "We offer"],
            rows)


def run(v) -> StandardResult:
    v = apply_site_system(v)
    horizon = int(v["finance.horizon"])
    rd = int(round(v["company.rd_years"]))
    sched = v["factory.schedule"]
    rate = v["finance.company_discount_rate"]
    site_cost = v["bench.site_built_cost_per_sqft"]
    p_sqft = price_per_sqft(v)
    shares = region_shares(v)
    offer = {r: chosen_package(v, r) for r in REGIONS}
    pkg = {r: package_price_cost(v, offer[r]) for r in REGIONS}
    cum_vpp_kw_value = 0.0  # sum over battery homes of kW x regional $/kW-yr
    cap = v["market.single_family_completions"] * v["market.max_share"]  # factory slots (home-equivalents)
    adu_share = v["adu.share_of_units"] * v["adu.enabled"]
    btr_share = v["btr.share_of_capacity"] * v["btr.enabled"]
    btr_cap = v["btr.market_starts"] * v["btr.max_share"] * v["btr.enabled"]
    p_btr = p_sqft * (1 - v["btr.price_discount"])

    experience = v["learning.first_year_experience"]
    build_years: list[int] = []
    life = int(v["factory.life"])
    tail: list[float] = []
    tail_open = True
    cum_retail_units = 0.0
    cumulative = 0.0
    learning_investment = 0.0
    noak_year = None
    rows: list[YearRow] = []

    # Years after the horizon count the remaining life of factories already built (same rule in all
    # three finalist TEAs): no new factories, factories retire at end of life, stop when cash turns negative.
    for t in range(1, horizon + life + 1):
        if t > horizon and not tail_open:
            break
        k = t - rd
        streams = {s: 0.0 for s in ("homes", "btr", "adus", "energy", "vpp", "service", "panels")}
        capex = 0.0
        active = sum(1 for b in build_years if t - b < life)
        if k >= 1 and (t <= horizon or active > 0):
            phase = "commercial"
            target = sched[min(k, len(sched)) - 1] if t <= horizon else active
            new = max(target - active, 0)
            build_years += [t] * new
            factories = active + new
            capex = new * v["factory.capex"]
            c = v["factory.capacity"]
            # Contracted BTR volume fills its share of each line first; retail fills the rest at the retail rate.
            # New factories are limited by their production ramp (first-year utilization).
            mature, new_total = (factories - new) * c, new * c * v["factory.first_year_utilization"]
            btr = min(mature * btr_share + min(new * c * btr_share, new_total), btr_cap, cap)
            retail = mature * (1 - btr_share) * v["factory.utilization"] + max(new_total - new * c * btr_share, 0.0)
            retail = min(retail, max(cap - btr, 0.0))
        else:
            phase, factories, btr, retail = "R&D", 0, 0.0, 0.0
        slots = btr + retail

        houses = retail * (1 - adu_share)
        adus = retail * adu_share / v["adu.slot_fraction"]
        units = btr + houses + adus
        idx = cost_index(v, experience)
        house_cost_sqft = site_cost * idx
        house_cogs = (houses + btr) * (v["home.sqft"] * house_cost_sqft - v["owner.gas_line_avoided"])
        adu_cogs = adus * v["adu.sqft"] * house_cost_sqft * v["adu.cost_premium"]
        learning_investment += ((houses + btr) * v["home.sqft"] + adus * v["adu.sqft"] * v["adu.cost_premium"]) * site_cost * (idx - noak_index(v))

        energy_homes = {r: houses * shares[r] * v["energy.take_rate"] * (offer[r] != "none") for r in REGIONS}
        battery_homes = {r: energy_homes[r] * (offer[r] == "solar + battery") for r in REGIONS}
        streams["homes"] = houses * v["home.sqft"] * p_sqft
        streams["btr"] = btr * v["home.sqft"] * p_btr
        streams["adus"] = adus * v["adu.sqft"] * v["adu.price_per_sqft"]
        streams["energy"] = sum(energy_homes[r] * pkg[r][0] for r in REGIONS)
        streams["vpp"] = cum_vpp_kw_value * v["vpp.enabled"] * v["vpp.enrollment"] * v["vpp.our_share"]
        streams["service"] = cum_retail_units * v["service.enabled"] * v["service.attach"] * v["service.fee_per_year"]
        streams["panels"] = factories * v["panels.enabled"] * v["panels.revenue_per_factory"]

        product_rev = streams["homes"] + streams["adus"] + streams["energy"]
        cos = (house_cogs + adu_cogs + sum(energy_homes[r] * pkg[r][1] for r in REGIONS)
               + product_rev * (v["company.selling_cost"] + v["company.warranty"])
               + streams["btr"] * (v["btr.selling_cost"] + v["company.warranty"])
               + (streams["homes"] + streams["btr"] + streams["adus"]) * financing_share(v)
               + streams["service"] * (1 - v["service.margin"])
               + streams["panels"] * (1 - v["panels.margin"])
               + factories * v["factory.fixed_opex"])
        revenue = sum(streams.values())
        gross = revenue - cos
        opex = v["company.rd_opex"] if phase == "R&D" else v["company.corporate_opex"] + revenue * v["company.ga_share"]
        ebit = gross - opex
        if t > horizon:
            if ebit - capex > 0:
                tail.append(ebit - capex)
            else:
                tail_open = False
            continue
        cumulative += ebit - capex
        rows.append(YearRow(t, phase, revenue, cos, gross, opex, ebit, cumulative, idx, streams, capex))
        final_homes = units

        experience += slots  # home-equivalents of line time
        cum_retail_units += houses + adus
        cum_vpp_kw_value += sum(battery_homes[r] * v["vpp.kw_per_home"] * v[f"region_{r}.vpp_payment"] for r in REGIONS)
        if noak_year is None and experience >= v["learning.noak_experience"]:
            noak_year = t

    cash = [r.ebit - r.capex for r in rows]
    npv_horizon = npv(rate, cash)
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
    site_on = bool(v.get("site_system.applied"))
    btr_margin = 1 - noak_full_cost(v, v["btr.selling_cost"]) / price_fu["Ours to build-to-rent buyers"]
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
        KillMetric("NOAK margin on homes after overhead, capex, selling, warranty, G&A and financing", margin, 0.10, "fraction",
                   margin >= 0.10, "10% threshold is a judgment (site-built builders averaged 11% in 2024)"),
        KillMetric("NOAK margin on build-to-rent homes", btr_margin, 0.10, "fraction", (not v["btr.enabled"]) or btr_margin >= 0.10,
                   "10% threshold is a judgment; BTR trades price for guaranteed volume" if v["btr.enabled"] else "BTR off in base; margin shown if switched on"),
        KillMetric("Assembled joint tolerance vs no-rework tolerance (prototype test)",
                   v["site_system.joint_tolerance_mm"], v["site_system.tolerance_needed_mm"], "mm (<= to win)",
                   (not site_on) or joints_ok(v),
                   "Fails -> finishing savings and the faster schedule are lost" if site_on else "Site system off"),
        KillMetric("Revenue at full scale vs big-enough line", rows[-1].revenue / big, 1.0, "x", rows[-1].revenue >= big),
    ]
    foak = {c: cost_multiplier(v["learning.first_year_experience"], v["learning.noak_experience"], _noak(v, c),
                               v[f"learning.rate_{c}"]) for c in COMPONENTS}
    return StandardResult(
        project="Automated factories for electrified prefab homes",
        years=rows,
        npv=npv(rate, cash + tail),
        irr=irr(cash + tail),
        peak_cash_need=-min(0.0, min(r.cumulative_cash for r in rows)),
        breakeven_year=breakeven_year,
        full_scale_revenue=rows[-1].revenue,
        functional_units=fus,
        learning={c: (foak[c], _noak(v, c)) for c in COMPONENTS},
        noak_year=noak_year,
        learning_investment=learning_investment,
        kill_metrics=kills,
        tables=[region_table(v)],
        notes=[
            f"Market check: year-{horizon} output is {final_homes:,.0f} homes/yr, vs ~30,000 modular + panelized homes built in the US in 2025 (3% of single-family).",
            "Energy package by region: each region gets the package that saves the owner most once it is financed in the mortgage, or none. Backup-power value is not counted.",
            "Cost multipliers are relative to the site-built construction cost (NAHB 2024: $162/sq ft); 'Cost vs incumbent' in the cash flow includes transport and set.",
            "Operating profit is before depreciation; factory capex is a separate cash outflow. Pre-tax, no working capital.",
            f"NPV includes the remaining life of factories built within the horizon (no new factories after it) "
            f"while cash stays positive; {len(tail)} tail years counted. NPV over the {horizon}-yr horizon alone: ${npv_horizon / 1e6:,.0f}M.",
            "Federal 45L and 25D credits ended in 2026, so no subsidies are counted.",
            "Build-to-rent: proposed federal limits on institutional home buyers could shrink this market; not modeled.",
            "Site system: an adjustable foundation must still meet frost-depth or engineered-foundation rules and count as a 'permanent foundation' for lenders and appraisers; not modeled.",
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
        ("site_system.foundation_reduction", -1.0, 0.95, "Foundation cost reduction for NPV = 0"),
    ]:
        out.append({"question": label, "input": key, "answer": breakeven(v, key, npv_of, 0.0, lo, hi), "base": v[key]})
    return out


def scenarios(v) -> list[tuple[str, dict]]:
    """Revenue add-ons, each switched on or off against the base case."""
    core = {"energy.enabled": 0, "vpp.enabled": 0, "service.enabled": 0, "panels.enabled": 0, "adu.enabled": 0}
    return [
        ("With build-to-rent offtake (25% of line, 7% discount)", {"btr.enabled": 1}),
        ("With build-to-rent offtake at a 3% discount", {"btr.enabled": 1, "btr.price_discount": 0.03}),
        ("Weak retail demand (60% fill), no build-to-rent", {"factory.utilization": 0.60}),
        ("Weak retail demand (60% fill), with build-to-rent", {"btr.enabled": 1, "factory.utilization": 0.60}),
        ("Conventional site work and crane set (no site system)", {"site_system.enabled": 0}),
        ("Site system, but joints miss tolerance", {"site_system.joint_tolerance_mm": 6.0}),
        ("Homes only (no add-ons)", core),
        ("+ Energy package", {**core, "energy.enabled": 1}),
        ("+ Energy package + VPP", {**core, "energy.enabled": 1, "vpp.enabled": 1}),
        ("Base case (energy + VPP + service)", {}),
        ("Base + panels for other builders", {"panels.enabled": 1}),
        ("Base + ADU line", {"adu.enabled": 1}),
        ("All add-ons", {"panels.enabled": 1, "adu.enabled": 1}),
    ]
