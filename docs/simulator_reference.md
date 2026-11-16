**SYNTHETIC DATA.** Everything this simulator produces is artificial. No real company, customer or campaign is behind it, and the parameter values are illustrative, not calibrated to any real business.

# Simulator reference

*Full reference for the simulator in this repository. Commands assume you run them from the repository root. Short version: [README](../README.md).*

*By Mabelly Tuchsznajder · All Else Equal Analytics · Marketing analytics · Causal inference*

A Python simulator that generates a **weekly marketing mix modeling (MMM) dataset where the true effect of every channel is known**. It writes two files:

| File | Contents |
|---|---|
| `synthetic_mmm_data.csv` | The **observed** columns an analyst would receive: sales, spend, impressions, clicks, a promo flag, calendar terms. |
| `ground_truth.json` | The **hidden truth**: every parameter, each channel's weekly contribution, and diagnostics of how the data was built. |

You fit an MMM on the first file, then score it against the second.

## Why this exists

On real client data, the true effect of advertising is unobservable, so there is no way to check whether an MMM is right. Simulated data closes that gap: if you know the truth, you can measure how far a model's *estimated contribution* is from it.

Most simulated examples make spend random, which removes the hardest part of the problem. In practice budgets follow seasons, promotions and recent sales, so spend and sales move together for reasons that are not advertising. This simulator builds that in, plus a hidden demand shock a model cannot see directly, and a Search channel whose click counts include people who would have bought anyway.

It is meant for testing modeling choices (spend vs. impressions vs. clicks, which controls to include, which estimator) against a known answer, and for teaching.

## Quickstart (about 5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Option A: command line
python src/simulate_mmm.py --config configs/config_v1.yaml --outdir data

# Option B: notebook (charts and checks included)
jupyter lab notebooks/01_generate_dataset.ipynb
```

Tested on Python 3.13 with numpy 2.1.3 / pandas 2.2.3 and with numpy 2.5.3 / pandas 3.0.5. The default dataset was byte-identical on both. Other versions are untested.

Command-line options:

| Option | Meaning |
|---|---|
| `--config PATH` | Config file. Default `config_v1.yaml` in the current folder. |
| `--seed N` | Random seed. Default is `seeds.primary` in the config. |
| `--outdir DIR` | Where to write the two files. Default is the current folder. |
| `--no-confounding` | Switch off performance-chasing and Search demand tracking (a sanity check). |

From Python:

```python
from simulate_mmm import simulate, load_config

cfg, sha = load_config("configs/config_v1.yaml")
obs, truth = simulate(cfg, seed=3, config_sha256=sha)  # obs: DataFrame, truth: dict
```

The command line prints a one-screen summary. For the default config and seed 2026:

```
SYNTHETIC data | config v1.0.0 | seed 2026 | confounding=True
channel          mean spend ROAS design ROAS real. share sales   r(Z)  r(logd)  r(noise)
tv                     60.4        1.83       1.81       0.076   0.74     0.00     -0.12
ooh                    19.8        1.77       1.77       0.025   0.64    -0.03     -0.18
meta                   40.4        1.99       1.86       0.053   0.73     0.01     -0.11
youtube_display        29.2        1.50       1.47       0.030   0.61     0.05     -0.12
search                 25.4        3.06       2.94       0.052   0.60     0.24     -0.09
all media share of sales: 0.236
search clicks not incremental: 0.394
```

## Main features

- **Seeded and reproducible.** The same config and seed give byte-identical files. Each random component has its own stream derived from the seed. The config's SHA-256 hash is stored in the truth file.
- **Mixed exposure metrics.** TV and OOH are spend-only. Meta and YouTube/display report impressions and spend. Search reports clicks and spend.
- **Time-varying prices.** Impressions are spend divided by a CPM that moves with the season and with auction noise. Search clicks use a CPC the same way. So a channel's spend and its exposure are related but not identical.
- **Carryover and diminishing returns.** Each channel's effect acts on its *exposure* variable through adstock (geometric by default, delayed optional) and a Hill saturation curve.
- **Endogenous spend.** Budgets follow the season, ramp up the week before a promotion, chase last week's sales (algorithmic channels), and, for Search, track a hidden demand shock.
- **A Search bias to study.** Observed Search clicks mix incremental clicks (driven by spend) with clicks from existing demand. Sales respond only to the incremental ones. An observed, noisy `organic_search_volume` column lets you test the standard fix of controlling for query volume.
- **Observed and hidden kept apart.** Every hidden series is prefixed `true_` and lives only in the JSON. A self-check fails the run if any hidden column reaches the CSV.
- **Confounding switch.** One flag turns the hidden confounding off so you can check that your model recovers the truth when the problem is easy.
- **Fully configurable.** Calendar, baseline, promotions, budget rules, and every channel are set in one YAML file. See [`config_guide.md`](config_guide.md).

## What the CSV contains (observed)

Default config: 156 weeks, 18 columns. Money is in thousand USD, impressions in millions, clicks and queries in thousands.

| Column | Meaning |
|---|---|
| `week_start` | Monday that starts the week |
| `t` | Week number from 0 (linear trend) |
| `sales` | Weekly sales, the KPI |
| `tv_spend`, `ooh_spend` | Weekly spend |
| `meta_spend`, `meta_impressions` | Spend and impressions |
| `youtube_display_spend`, `youtube_display_impressions` | Spend and impressions (video and display combined) |
| `search_spend`, `search_clicks` | Spend and clicks (clicks include non-incremental ones) |
| `organic_search_volume` | Search queries: a noisy measure of demand, usable as a control |
| `promo_flag` | 1 in promotion weeks |
| `holiday_flag` | 1 in the Black Friday week and the week containing Dec 24 |
| `fourier_sin1`, `fourier_cos1`, `fourier_sin2`, `fourier_cos2` | Seasonality terms (two harmonics of the day of the year) |

## What the JSON contains (ground truth)

| Key | Contents |
|---|---|
| `SYNTHETIC_DATA`, `config_version`, `config_sha256`, `seed`, `confounding_enabled` | Provenance. |
| `parameters` | The channel, baseline, promo, budget and search settings used. |
| `promo_events` | Each promotion: name, year, weeks, and the uplift drawn for it. |
| `design_values_typical_week` | Average and marginal ROAS implied by the config at a typical week's carryover level. |
| `realized` | Per channel: mean spend, total contribution, **realized average ROAS**, share of sales, and correlations of spend with the seasonal index, promo flag, hidden demand shock and sales noise. Also the share of Search clicks that are not incremental. |
| `weekly` | 29 hidden weekly series, all prefixed `true_`: baseline, demand shock, promo uplift, sales noise, seasonal index, true query volume, incremental and demand-driven Search clicks, and per channel the true exposure, price, adstocked exposure and **contribution**. |

**Score models against the realized values.** Realized ROAS is a channel's total contribution divided by its total spend over the period. The design values differ slightly because of diminishing returns and timing.

## How the data is generated

For week *t* and channel *c*:

```
baseline_t    = start_level × (1 + trend_per_year × t/52) × (1 + seasonal_t + holiday_t)
demand_t      = baseline_t × d_t                 d_t = exp(AR(1)): a hidden demand shock
promo_t       = promo_flag_t × uplift_event × baseline_t
noise_t       = sd_frac × baseline_t × AR(1)_t
sales_t       = demand_t + promo_t + Σ_c contribution_c,t + noise_t

contribution  = beta_c × Hill( adstock( exposure_c ) )
exposure_c    = spend_c / price_c                (price = CPM or CPC; 1 for spend-only channels)
adstock       = Σ_l w_l × exposure_(t-l)         52 lags; geometric w_l = decay^l
Hill(a)       = a^s / (a^s + k^s)                s = shape, k = half-saturation level

spend_c,t     = norm_c × calendar_c,t × chase_c,t × tracking_c,t × planning_noise_c,t
calendar      = max(floor, 1 + season_sens × Z_t + promo_sens × P_t)
chase         = max(floor, 1 + chase_c × g_t)    g_t: last week's sales vs the 4 weeks before, clipped
tracking      = max(floor, 1 + latent_tracking × log d_t)     Search only, by default
```

`Z_t` is the seasonal index scaled to run from about -0.51 to +1.0. `P_t` is 1 in promotion weeks and 0.5 in the week before a promotion starts. Planning noise is the only spend variation that is unrelated to the calendar or to hidden demand, which is what makes any media effect identifiable at all.

Search has three extra pieces:

```
incremental_clicks    = search_spend / CPC                         drives sales
search_clicks (obs.)  = incremental_clicks + demand_click_share × true_query_volume
organic_search_volume = true_query_volume × exp(proxy_noise_sd × N(0,1))
```

Because sales respond only to incremental clicks, a model fit on observed clicks is expected to be biased by construction. The simulator makes that mechanism explicit; it does not prove how large the bias is in real accounts.

## Repository layout

```
.
├── README.md
├── requirements.txt
├── configs/config_v1.yaml            default config (v1.0.0)
├── data/                             default dataset: config v1.0.0, seed 2026
│   ├── synthetic_mmm_data.csv
│   └── ground_truth.json
├── docs/config_guide.md              every config key, tested recipes, error messages
├── notebooks/01_generate_dataset.ipynb
└── src/simulate_mmm.py
```

## Limitations (read before drawing conclusions)

- **Parameters are illustrative.** None are calibrated to a real business or to published benchmarks. Do not quote the effect sizes as realistic.
- **Seasonality and trend are easy to model.** The CSV ships the exact Fourier terms and a linear `t` that generate them. Real seasonality is rarely this tidy, so recovery here is optimistic.
- **Simple response shapes.** Saturation is a concave Hill curve (shape 1) by default and carryover is geometric. S-shaped curves and delayed carryover are configurable but not in the default config.
- **No synergies.** Channel effects add up. There are no interactions, no cannibalisation and no pull-forward dip after promotions.
- **One curve for YouTube and display.** They are combined into a single channel.
- **Search is constructed, not observed.** Demand-driven clicks are assumed to have zero effect on sales, and query volume is driven by baseline demand only, with no lift from other media.
- **Performance-chasing is weak in the default config.** Across seeds 1 to 20, spend correlates with the hidden demand shock at about 0.2 for Search and about zero for the other channels. Search is the channel where the hidden confounding is strong enough to matter.
- **Clean data.** No missing weeks, outliers, definition changes or measurement error in spend or sales.
- **One market.** No geography, price changes, competitor activity or macro controls.
- **One seed is one draw.** A single dataset cannot separate a model's bias from bad luck. Repeat over many seeds before claiming a model is biased or unbiased.
- **Carryover has no cold start.** Pre-sample exposure is set to the channel's average.

## Describing results honestly

| Say | Avoid |
|---|---|
| "The model recovers the known effect of Search to within X% in this simulation." | "The model proves paid search drives sales." |
| "Estimated contribution of TV is X; the simulated contribution is Y." | "TV caused X of sales." |
| "Controlling for query volume reduced the bias under this simulated mechanism." | "Controlling for query volume fixes MMM." |
| "On this one dataset." | Any claim that generalises to real accounts. |

## References

- Heusch, N. (2026). *A Synthetic Benchmark Dataset with Endogenous Marketing Spend for Validating Marketing Mix Models.* arXiv:2608.21130 (preprint). Source of the idea of recording the true decomposition alongside the observed variables and of building spend endogenously. This simulator is an independent reimplementation from the documented ideas, not a copy of that work's code.
- Jin et al. (2017). [*Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects.*](https://research.google/pubs/bayesian-methods-for-media-mix-modeling-with-carryover-and-shape-effects/) Google Research. Source of the geometric and delayed adstock and Hill saturation forms.
- Google Meridian documentation: [Paid search modeling](https://developers.google.com/meridian/docs/advanced-modeling/paid-search-modeling). Query volume as a confounder for paid search.

## Contact

Mabelly Tuchsznajder · All Else Equal Analytics · mabelly@allelseequal.com · [LinkedIn](https://www.linkedin.com/in/motsci)
