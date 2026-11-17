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

| Metric | Value |
|---|---|
| NPV (10%, 15 yr) | $147M |
| IRR | 19% |
| P(NPV > 0), Monte Carlo | 26% |
| Peak cash need | $266M |
| Cash breakeven | year 11 |
| Year-15 revenue | $2.09B (about 6,300 homes/yr from 33 factories) |
| Extra cost paid while learning | $255M |

**Versus incumbents ($/sq ft, excluding land):** ours $175 price and $156 NOAK
full cost; conventional modular $184; site-built $217. Permit to occupancy:
4.5 months, against 6.9 for modular and 8.8 for site-built.

All five kill metrics pass at base. The weak point is the probability: the base
case sits near the optimistic end of several ranges (factory capex, learning
volume), so the Monte Carlo median is negative (P50 −$214M).

**What decides it** (break-evens for NPV = 0):

- Factory capex at most $21M per 250-home/yr plant. Reframe-style microfactories (<$5M equipment, company-reported) pass; $40–60M ground-up plants fail.
- Utilization at least 61%. Katerra and Veev failed on demand and overhead, not on robots.
- Price discount vs modular at most 8.8%.
- MEP cost reduction at least 4% (base 25%).
- Tornado leaders: factory capacity, factory capex, price discount, the modular discount benchmark, and how many homes it takes to reach NOAK.

## Revenue add-ons (NPV, modeled)

| Scenario | NPV |
|---|---|
| Homes only | $101M |
| + solar + battery package | $144M |
| + VPP aggregation share | $146M |
| Base (energy + VPP + service) | $147M |
| Base + panels sold to other builders | $173M |
| Base + ADU line | $196M |
| All add-ons | $221M |

The energy package earns the company margin, but owners only come out ahead
above about $0.215/kWh (base $0.165, US average). In high-rate states like
California it pays. VPP and service subscriptions are small at this scale.

**Not yet modeled, worth testing next:** build-to-rent offtake contracts (fixes
utilization), mortgage origination, factory software licensing, disaster-rebuild
contracts, wildfire-hardened homes with insurer partnerships, and climate-specific
variants.

## Caveats

- Pre-tax, real 2026 USD; no depreciation, working capital or terminal value.
- Costs are benchmarked to NAHB 2024 site-built construction cost ($162/sq ft); NOAK reductions are targets, not measured.
- Federal 45L and 25D credits ended in 2026 and are not counted.
- Solar output is valued at the retail rate, which flatters the package under net billing.

## Layout

```
inputs/          conventions.toml (shared) and prefab_homes.toml
tea/framework/   learning curves, uncertainty, report writer
tea/prefab_homes.py
scripts/run_tea.py
results/prefab_homes/   summary.md, cashflow.csv, sensitivity.csv, tornado.png, monte_carlo.png
docs/framework.md
```
