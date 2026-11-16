**Synthetic data.** Every config value below is illustrative. The simulator was tested at the shipped values and at the variations listed in section 5. Other values may work but are untested.

# Config guide

The whole simulated business lives in one YAML file. This guide explains every key, shows how to choose numbers, lists recipes that were tested, and decodes the error messages you are most likely to meet.

## 1. Three rules

1. **Freeze the config before you fit any model.** If you change a value after seeing results, you are tuning the data to the answer.
2. **A changed value is a new version.** Copy the file (`config_v1_1.yaml`), bump `config_version`, and list what changed in the header comment. Keep every version.
3. **Report diagnostics, never tune to them.** The printed correlations and ROAS values describe the dataset. They are not targets.

Every run stores the config's SHA-256 hash in `ground_truth.json`, so a dataset can be traced to the exact file that made it.

## 2. Units

| Quantity | Unit |
|---|---|
| Money (spend, sales, contributions) | thousand USD |
| Impressions | millions |
| Clicks, search queries | thousands |
| CPM | USD per thousand impressions |
| CPC | USD per click |
| Weeks | calendar weeks starting Monday |

Why the numbers line up: 40 (thousand USD) divided by a CPM of 8 gives 5.0 million impressions. 25 (thousand USD) divided by a CPC of 1.00 gives 25 thousand clicks.

The default config describes a retailer with mean weekly sales near 1.4 million USD (1,426 thousand in the default dataset), with media spend at about 12% of sales.

## 3. Reference

### Top level

| Key | Meaning |
|---|---|
| `config_version` | Free text label, stored in the truth file. Bump it whenever you change a value. |
| `seeds.primary` | Seed used when you do not pass `--seed`. |
| `seeds.multi` | A list of seeds. **The simulator does not read it.** It is a place to fix, in advance, the seeds you will loop over in your own multi-seed runs. |
| `confounding.enabled` | `true`: spend chases sales and Search tracks hidden demand. `false`: both set to zero (a sanity check). The `--no-confounding` flag overrides it. |

### `calendar`

| Key | Meaning |
|---|---|
| `start_date` | First week, in quotes. **Must be a Monday.** |
| `n_weeks` | Number of weeks. If you change it, also check `promos.expected_promo_weeks` (see section 5). |

### `baseline`

| Key | Meaning | Default |
|---|---|---|
| `start_level` | Weekly sales at week 0 before seasonality, shocks and media. | 1000 |
| `trend_per_year` | Linear growth: baseline is multiplied by `1 + trend_per_year × t/52`. | 0.05 |
| `seasonality.peak_day_of_year` | Day of the year of the seasonal peak (330 is about Nov 26). | 330 |
| `seasonality.harmonic1_amp` | Size of the main seasonal wave, as a fraction of baseline. | 0.10 |
| `seasonality.harmonic2_amp` | Size of the second wave, same phase, which sharpens the peak. | 0.04 |
| `holidays.black_friday_bump` | Fraction of baseline added in the Black Friday week. | 0.15 |
| `holidays.pre_christmas_bump` | Fraction of baseline added in the week containing Dec 24. | 0.10 |
| `latent_demand.rho` | Persistence of the hidden demand shock (0 to under 1). | 0.70 |
| `latent_demand.sd` | Size of the hidden demand shock (standard deviation of its log). | 0.03 |
| `noise.rho` | Persistence of the sales noise. | 0.30 |
| `noise.sd_frac` | Sales noise as a fraction of baseline. | 0.04 |

The holiday dates are fixed in the code: only the Black Friday week and the week containing Dec 24. You can change their sizes but not add holidays through the config.

Realized values vary by seed. In the default dataset the hidden shock's standard deviation came out at 0.026 rather than 0.03, and the sales noise at 3.7% of baseline rather than 4%.

### `promos`

| Key | Meaning |
|---|---|
| `uplift_mean`, `uplift_sd` | Each promotion event draws one uplift from a normal with these values, as a fraction of that week's baseline. |
| `expected_promo_weeks` | A guard: the run **fails** if the number of promotion weeks differs from this. |
| `events` | The promotion calendar, repeated every year. |

Event types:

```yaml
- {name: spring_sale, type: nth_mondays, month: 4, nths: [2, 3]}   # 2nd and 3rd week starts in April
- {name: black_friday, type: black_friday}                           # the Black Friday week
```

`nths` counts the week starts (Mondays) inside that month, from 1. A position that does not exist in a given month is silently skipped, so always check the count. The default calendar gives 6 promotion weeks per year, 18 over 156 weeks. A promotion week that is also a holiday week gets both effects.

### `budget_rules` (shared by all channels)

| Key | Meaning | Default |
|---|---|---|
| `multiplier_floor` | Each spend multiplier is clipped at this minimum. | 0.2 |
| `anticipation_level` | Promo ramp in the week before a promotion starts (it is 1.0 during). | 0.5 |
| `chase_ref_weeks` | Last week's sales are compared with the average of the previous this-many weeks. | 4 |
| `chase_clip` | The comparison is clipped to plus or minus this fraction. | 0.20 |

### `channels.<name>`

You can name channels anything. Each one produces `<name>_spend`, plus `<name>_impressions` or `<name>_clicks` depending on `exposure`.

| Key | Meaning |
|---|---|
| `exposure` | `spend`, `impressions` or `clicks`. What the channel's effect acts on. **Spell it exactly** (see section 6). |
| `mean_spend` | Target average weekly spend. The realized mean lands within a few percent (60.0 became 60.4 for TV). |
| `price` | Needed for `impressions` and `clicks`; omit it for `spend`. |
| `price.kind` | A label (`cpm` or `cpc`). **Not read by the simulator.** |
| `price.base` | CPM or CPC in the units above. |
| `price.q4_amp` | Price rises by this fraction in proportion to the seasonal index wherever it is positive. A seasonal effect, not strictly October to December. |
| `price.ar_rho`, `price.log_sd` | Persistence and size of week-to-week auction noise (in logs). |
| `adstock.type` | `geometric` (peaks in the spend week, then decays) or `delayed` (peaks `peak_lag` weeks later). |
| `adstock.decay` | Carryover, from 0 up to but excluding 1. Larger means longer memory. |
| `adstock.peak_lag` | Delayed only: the week of maximum effect. 0 means the same week. |
| `saturation.k` | The adstocked exposure level at which the channel reaches half of `beta`. |
| `saturation.shape` | 1 is a concave curve. Above 1 gives an S-shaped curve. |
| `beta` | The most a channel can contribute in a week (thousand USD), approached as exposure grows without limit. |
| `budget.season_sens` | How strongly spend follows the seasonal index. |
| `budget.promo_sens` | How strongly spend rises in and just before promotion weeks. |
| `budget.planning_noise_sd` | Random planning variation in spend. **Never set it to zero:** it is the only spend variation unrelated to the calendar and to hidden demand, so without it no media effect can be identified. |
| `budget.chase` | How strongly spend follows last week's sales performance. 0 means planned in advance. |
| `budget.latent_tracking` | Optional (default 0). How strongly spend follows the hidden demand shock. Used for Search. |

### `search_demand`

| Key | Meaning | Default |
|---|---|---|
| `channel` | Name of the channel that receives demand-driven clicks. **It must exist and have `exposure: clicks`.** | `search` |
| `query_volume_at_start` | Search queries per week (thousands) when baseline demand is at its starting level. | 300 |
| `proxy_noise_sd` | Noise in the observed `organic_search_volume`, as a multiplicative log-normal. | 0.10 |
| `demand_click_share` | Share of true query volume that shows up as ad clicks from people who would have bought anyway. | 0.05 |

Observed Search clicks equal incremental clicks plus demand-driven clicks. Sales respond only to the incremental clicks.

## 4. Choosing numbers for a channel

Work in this order. Worked example for the default TV channel (spend-only):

| Step | Rule | TV example |
|---|---|---|
| 1. Typical adstock level | `mean exposure / (1 − decay)` | 60 / (1 − 0.6) = **150** |
| 2. Put the channel mid-curve | Set `saturation.k` near the typical level | k = 150, so Hill = 150 / (150 + 150) = **0.5** |
| 3. Pick the size | Typical weekly contribution = `beta × Hill` | 220 × 0.5 = **110** per week |
| 4. Check the return | Average ROAS = contribution / mean spend | 110 / 60 = **1.83** |
| 5. Check diminishing returns | Marginal ROAS (shape 1) = `beta × k / (a + k)² × 1/(1 − decay) / price`, where `a` is the typical level from step 1 and `price` is 1 for spend-only channels | 220 × 150 / 300² × 2.5 = **0.92** |

Half-life of carryover in weeks = ln(0.5) / ln(decay). A decay of 0.6 gives about 1.4 weeks; 0.3 gives about 0.6.

For a **delayed** channel, the weights are `decay^((lag − peak_lag)²)`, rescaled to the same total as the geometric case, so `k` and `beta` keep their meaning. Here `decay` sets the width of the bump around the peak, not a half-life, so do not reuse a geometric value unchanged.

For an impressions or clicks channel, use `exposure = spend / price` in step 1, with `price.base` as the typical price. Then check three things in the printed summary: the realized ROAS is plausible, the channel's share of sales is plausible, and **all media together** is a believable share of sales (23.6% in the default data). Large `beta` values pass every automatic check and still give an absurd business.

## 5. Recipes (tested)

Each of these was run on the default config and checked.

| I want to | Change | What happened |
|---|---|---|
| Another dataset from the same business | `--seed 7`, or edit `seeds.primary` | New draw. Same rules. |
| A 2-year series | `n_weeks: 104` and `expected_promo_weeks: 12` | Ran. With `expected_promo_weeks` left at 18, the run **failed** and wrote nothing. |
| A 4-year series | `n_weeks: 208` and `expected_promo_weeks: 24` | Ran. |
| A sanity check with no hidden confounding | `confounding.enabled: false` or `--no-confounding` | Ran. Averaged over seeds 1 to 20, the correlation of Search spend with hidden demand fell from 0.21 to -0.05. |
| Delayed TV carryover | `tv.adstock: {type: delayed, decay: 0.6, peak_lag: 1}` | Ran. Weights peak at lag 1 and carry the same total mass as geometric. |
| S-shaped saturation for one channel | `saturation.shape: 2.0` | Ran. Recheck ROAS and media share, because the shape changes them. |
| Add a spend-only channel | A new block under `channels` with `exposure: spend` | Ran. Adds `<name>_spend`. |
| Add a second clicks channel | New block with `exposure: clicks` and a `price` block | Ran. Adds `_spend` and `_clicks`. It does **not** get demand-driven clicks. Only `search_demand.channel` does. |
| Drop a channel | Delete its block, for example `ooh` | Ran. Media share fell from 23.6% to 21.7%. |
| Less accurate query-volume proxy | `proxy_noise_sd: 0.4` | Observed volume tracked true volume with correlation 0.29 (seed 2026). |
| A perfect query-volume proxy | `proxy_noise_sd: 0.0` | Correlation 1.00. |

**Note on the proxy default.** At the default `proxy_noise_sd` of 0.10, the correlation between observed and true query volume is 0.74 (seed 2026). The reason: true query volume itself varies by only about 10% (standard deviation, seed 2026), so 10% noise puts signal and noise on equal footing. If you want a proxy that is good but not perfect, expect to need a value well below 0.10.

### Stronger Search confounding (optional)

Three values together make Search spend follow hidden demand more closely. Measured on seeds 1 to 20, simulator only, with no models fitted:

| Level | `latent_demand.rho` | `latent_demand.sd` | `search.budget.latent_tracking` | Correlation of Search spend with hidden demand | Total sales noise |
|---|---|---|---|---|---|
| Weak (default) | 0.70 | 0.03 | 2 | 0.21 | about 5.0% |
| Medium | 0.85 | 0.04 | 3 | 0.34 | about 5.7% |
| Strong | 0.90 | 0.05 | 4 | 0.50 | about 6.4% |

Read these caveats before using them:

- **The levels were chosen against a guardrail that was relaxed after seeing the results.** The Search spend multiplier was meant to stay between 0.5 and 1.5 for 90% of weeks. That made the medium and strong levels unreachable, so the upper bound was raised to 1.65. The medium level reaches 1.51 and the strong level 1.61.
- **Only Search gets stronger.** Meta and YouTube/display performance-chasing stays weak at every level.
- **One seed cannot tell the levels apart.** The spread across seeds (about 0.12 to 0.14) is as large as the gaps between levels.
- **Everything gets harder to estimate** as the hidden shock grows, OOH most of all. This is an expectation from the design (OOH has the smallest signal against the noise), not something measured, because no models were fitted.
- "Total sales noise" is the combined size of the sales noise (4%) and the hidden shock, as the square root of the sum of their squared standard deviations. It is derived from the config, not measured.

## 6. Errors and what they mean

| What you see | Cause | Fix |
|---|---|---|
| `ValueError: calendar.start_date must be a Monday` | The start date falls on another weekday. | Pick a Monday. |
| `ValueError: unknown adstock type: X` | `adstock.type` is not `geometric` or `delayed`. | Fix the spelling. |
| `AssertionError: promo week count drifted` | The number of promotion weeks differs from `expected_promo_weeks`. | Count them (`obs.promo_flag.sum()`) and update the key. Nothing is written when this fails. |
| `AssertionError: non-positive sales` | Noise or other terms are large enough to push sales to zero or below. | Lower `noise.sd_frac` or `latent_demand.sd`. A noise of 0.5 triggers it. |
| `KeyError: 'price'` | A channel has `exposure` set to something other than `spend` but no `price` block, or `exposure` is misspelled. | Add `price`, or fix the spelling. |
| `KeyError: 'beta'` (or another key name) | A required key is missing from a channel. | Add it. Every channel needs `exposure`, `mean_spend`, `adstock`, `saturation`, `beta` and `budget`. |
| `KeyError: 'search'` | `search_demand.channel` names a channel that no longer exists. | Point it at an existing channel with `exposure: clicks`, or keep the channel. Removing every clicks channel is not supported. |
| `ZeroDivisionError` | `adstock.decay` is 1.0. | Use a value below 1. |

### Two mistakes that raise no error

1. **A misspelled `exposure` is silently accepted if the channel has a `price` block.** For example, `impresions` ran without complaint and the channel produced `meta_spend` but **no `meta_impressions` column**. After any change, check that the columns you expected are in the CSV.
2. **An implausible business passes every check.** A TV `beta` of 5000 ran cleanly and put media at 71% of sales. The automatic checks look for malformed data, not for realism. Read the printed summary every time.

## 7. Before you share a dataset

- [ ] The config version is bumped and the changes are listed in its header.
- [ ] The run printed the summary and raised no assertion.
- [ ] The CSV has the columns you expect, and none starts with `true_`.
- [ ] Media's share of sales and each channel's ROAS are plausible for the business you mean to mimic.
- [ ] The README or post says **synthetic** in the first line and says the parameters are illustrative.
- [ ] Results are worded as "recovers the known effect" or "estimated contribution", for this simulation only.
