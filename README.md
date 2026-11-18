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
| NPV (10%, 15 yr) | $361M |
| IRR | 28% |
| P(NPV > 0), Monte Carlo | 43% |
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
| Conventional site work and crane set | $85M |
| Site system, but assembled joints miss the no-rework tolerance | $309M |
| Site system working (base) | $361M |

Most of the gain comes from the foundation and the forklift set. The joint-tolerance
kill metric (assembled joints within ~3 mm, to be proven in a prototype) protects
the finishing savings and the extra month of speed.

**What decides it** (break-evens for NPV = 0):

- Factory capex at most $37M per 250-home/yr plant.
- Utilization at least 45%. Katerra and Veev failed on demand and overhead, not on robots.
- Price discount vs modular at most 14%.
- Tornado leaders: factory capacity, factory capex, price discount, and how many homes it takes to reach NOAK.
- The Monte Carlo median is still negative (P50 −$49M): the base case sits near the optimistic end of the factory-capex and learning ranges.

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
$13M of NPV. Backup-power value is not counted.

## Revenue add-ons (NPV, modeled)

| Scenario | NPV |
|---|---|
| Homes only | $346M |
| Base (regional energy + VPP + service) | $361M |
| Base + panels sold to other builders | $386M |
| Base + ADU line | $415M |
| All add-ons | $440M |

**Not yet modeled, worth testing next:** build-to-rent offtake contracts (fixes
utilization), mortgage origination, factory software licensing, disaster-rebuild
contracts, wildfire-hardened homes with insurer partnerships, and climate-specific
variants.

## Caveats

- Pre-tax, real 2026 USD; no depreciation, working capital or terminal value.
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
