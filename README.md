# Autonomously prefabricated homes: moonshot TEA

Techno-economic analysis of a network of robotic microfactories that build
all-electric single-family homes, with optional factory-installed solar and
batteries and recurring revenue from the homes delivered.

The model uses the same standard TEA framework as
[thermosyphon-moonshot](https://github.com/mallorysnowden/thermosyphon-moonshot):
NOAK unit costs, Wright's-law learning from FOAK, BAU comparisons, tornado,
Monte Carlo, break-evens, kill metrics and a weighted scorecard.

## Run it

```bash
pip install -r requirements.txt
python scripts/run_tea.py prefab_homes          # writes results/prefab_homes/
python -m pytest
```

Change inputs in `inputs/prefab_homes.toml` (every input has a range and a source,
or is marked "Assumption").

## Requirements tested

1. Cost-competitive with conventionally built prefab (modular), before counting lower energy bills.
2. Shorter time from permit to occupancy than a conventional home.
3. Profit margin per house, and whether the business clears the "big-enough" line ($1B/yr revenue, a judgment).

## Results (base case)

The base case includes the **site system**: a self-leveling foundation and
forklift-set components that lock together with almost no onsite finishing.

| Metric | Value |
|---|---|
| NPV (10%), incl. remaining factory life | $876M |
| NPV over the 15-yr horizon only | $360M |
| IRR | 32% |
| P(NPV > 0), Monte Carlo | 71% |
| Peak cash need | $237M |
| Cash breakeven | year 10 |
| Year-15 revenue | $2.02B (about 6,300 homes/yr from 33 factories) |
| Extra cost paid while learning | $296M |

**Versus incumbents ($/sq ft, excluding land):** ours $175 price and $143 NOAK
full cost (19% margin); conventional modular $184; site-built $217. Permit to
occupancy: 3.5 months, against 6.9 for modular and 8.8 for site-built, which saves
the buyer about $8,500 of rent or double payments vs modular.

**Where the breakthrough sits**

| Scenario | NPV |
|---|---|
| Conventional site work and crane set | $396M |
| Site system, but assembled joints miss the no-rework tolerance | $784M |
| Site system working (base) | $876M |

Most of the gain comes from the foundation and the forklift set. The joint-tolerance
kill metric (assembled joints within ~3 mm, to be proven in a prototype) protects
the finishing savings and the extra month of speed.

**What decides it** (break-evens for NPV = 0):

- Factory capex at most $75M per 250-home/yr plant.
- Utilization at least 33%. Katerra and Veev failed on demand and overhead, not on robots.
- Price discount vs modular at most 18.5%.
- Tornado leaders: factory capacity, factory capex, price discount, and how many homes it takes to reach NOAK.
- Monte Carlo P10 / P50 / P90: −$288M / $294M / $1.11B.

## Build-to-rent offtake (scenario)

Rental operators contract 25% of each factory's line at a 7% bulk discount, with
almost no selling cost; retail buyers fill the rest. US single-family built-for-rent
starts were 68,000 in 2025 (NAHB), so our ~2,000 homes/yr would be about 3% of it.

| Scenario | NPV |
|---|---|
| Retail only (base) | $876M |
| + build-to-rent at 7% discount | $871M |
| + build-to-rent at 3% discount | $955M |
| Weak retail demand (60% fill), retail only | $503M |
| Weak retail demand (60% fill), + build-to-rent | $592M |

Build-to-rent is insurance, not profit: at a 7% discount it beats retail-only only
when retail demand fills less than ~79% of the line. It lowers the utilization
needed for NPV = 0 from 33% to 18%. The anchor
contracts could also speed each new factory's ramp, which is not credited here.
Policy risk: proposed federal limits on institutional home buyers could shrink
this market.

## Energy package by region

Each region gets the package that saves the owner most once it is financed in the
mortgage (no federal credit), or none.

| Region | Share of sales | Owner gain, solar only | Owner gain, solar + battery | Offered |
|---|---|---|---|---|
| CA / HI (net billing) | 8% | $887/yr | $1,145/yr | solar + battery |
| New England / NY (net metering, battery programs) | 5% | $921/yr | $707/yr | solar |
| Southeast (full net metering) | 35% | $156/yr | −$671/yr | solar |
| Texas-style buyback | 27% | −$61/yr | −$408/yr | none |
| Mountain / Midwest (cheap power, net billing) | 25% | −$359/yr | −$927/yr | none |

The package fits best where the fewest new homes are built. It adds only about
$22M of NPV. Backup-power value is not counted.

## Revenue add-ons (NPV, modeled)

| Scenario | NPV |
|---|---|
| Homes only | $850M |
| Base (regional energy + VPP + service) | $876M |
| Base + panels sold to other builders | $917M |
| Base + ADU line | $968M |
| All add-ons | $1.01B |

**Not yet modeled, worth testing next:** mortgage origination, factory software licensing, disaster-rebuild
contracts, wildfire-hardened homes with insurer partnerships, and climate-specific
variants.

## Caveats

- Pre-tax, real 2026 USD; no depreciation or working capital. NPV counts the remaining
  life of factories built within the horizon (no new factories after it) while cash stays
  positive, the same rule used in the thermosyphon and SAF TEAs.
- Costs are benchmarked to NAHB 2024 site-built construction cost ($162/sq ft); NOAK reductions are targets, not measured.
- Federal 45L and 25D credits ended in 2026 and are not counted.
- Solar self-use share (60%) and battery cycling are assumptions, not an hourly load model.
- An adjustable foundation must still meet frost-depth or engineered-foundation rules and qualify as a "permanent foundation" for mortgages; not modeled.
- Construction financing is 1.5% of price on a site-built schedule (NAHB 2024), scaled to our build time.

## Layout

```
inputs/          conventions.toml (shared) and prefab_homes.toml
tea/framework/   learning curves, uncertainty, report writer
tea/prefab_homes.py
scripts/run_tea.py
results/prefab_homes/   summary.md, cashflow.csv, sensitivity.csv, tornado.png, monte_carlo.png
docs/framework.md
```

## Consistency audit (Nov 2026)

- Shared remaining-life rule with the thermosyphon and SAF TEAs: after the 15-year horizon, factories already built run out their 15-year life with no new builds, counted only while cash stays positive. Horizon-only NPV is still reported in `results/prefab_homes/summary.md`.
- Synced the shared framework (capex column, extra tables, include-aware `run_tea.py`).
- Already consistent: 10% real discount rate, 3% G&A, pre-tax, $1B big-enough line, 2,000 Monte Carlo draws.
