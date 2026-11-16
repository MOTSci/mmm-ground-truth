#!/usr/bin/env python3
"""
simulate_mmm.py | SYNTHETIC weekly Marketing Mix Model data generator.

ALL DATA PRODUCED HERE IS SYNTHETIC. Parameters are illustrative, not calibrated.

Reference for the idea of recording ground truth next to observed variables and of
endogenous spend: Heusch (2026), arXiv 2608.21130. This is an independent
reimplementation from the documented ideas, not a copy of that code.

Outputs
  synthetic_mmm_data.csv   observed columns only (what a practitioner would see)
  ground_truth.json        parameters, realized diagnostics and per-week hidden truth
                           (every hidden column is prefixed "true_")

Usage
  python simulate_mmm.py --config config_v1.yaml                 # primary seed
  python simulate_mmm.py --config config_v1.yaml --seed 7        # another seed
  python simulate_mmm.py --config config_v1.yaml --no-confounding

Import use (multi-seed runs):
  from simulate_mmm import simulate, load_config
  cfg, sha = load_config("config_v1.yaml")
  obs, truth = simulate(cfg, seed=3, config_sha256=sha)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ADSTOCK_LAGS = 52  # truncation of carryover weights (mass beyond this is negligible)


# --------------------------------------------------------------------------- helpers
def ar1(rng, n, rho, sd):
    """Stationary AR(1) series with marginal standard deviation `sd`."""
    out = np.empty(n)
    out[0] = rng.normal(0.0, sd)
    innov_sd = sd * np.sqrt(1.0 - rho**2)
    for t in range(1, n):
        out[t] = rho * out[t - 1] + rng.normal(0.0, innov_sd)
    return out


def mean_one_lognormal(rng, n, sd):
    return np.exp(sd * rng.standard_normal(n) - 0.5 * sd**2)


def carryover_weights(kind, decay, peak_lag=0, n_lags=ADSTOCK_LAGS):
    lags = np.arange(n_lags)
    if kind == "geometric":
        return decay**lags
    if kind == "delayed":
        w = decay ** ((lags - peak_lag) ** 2)
        return w * (1.0 / (1.0 - decay)) / w.sum()  # same total mass as geometric
    raise ValueError(f"unknown adstock type: {kind}")


def hill(a, k, shape):
    a_s = a**shape
    return a_s / (a_s + k**shape)


def hill_slope(a, k, shape, beta):
    """d(beta * hill)/da"""
    return beta * shape * k**shape * a ** (shape - 1.0) / (a**shape + k**shape) ** 2


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def load_config(path):
    raw = Path(path).read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()


# -------------------------------------------------------------------------- calendar
def black_friday(year):
    nov1 = pd.Timestamp(year, 11, 1)
    first_thu = nov1 + pd.Timedelta(days=(3 - nov1.weekday()) % 7)
    return first_thu + pd.Timedelta(days=22)  # fourth Thursday + 1 day


def week_index(dates, day):
    monday = day - pd.Timedelta(days=day.weekday())
    hit = np.where(dates == monday)[0]
    return int(hit[0]) if len(hit) else None


def build_calendar(cfg):
    start = pd.Timestamp(cfg["calendar"]["start_date"])
    if start.weekday() != 0:
        raise ValueError("calendar.start_date must be a Monday")
    return pd.date_range(start, periods=int(cfg["calendar"]["n_weeks"]), freq="W-MON")


def seasonal_terms(cfg, dates):
    s = cfg["baseline"]["seasonality"]
    doy = (dates + pd.Timedelta(days=3)).dayofyear.to_numpy().astype(float)  # mid-week
    phase = 2 * np.pi * (doy - s["peak_day_of_year"]) / 365.25
    seasonal = s["harmonic1_amp"] * np.cos(phase) + s["harmonic2_amp"] * np.cos(2 * phase)
    z = seasonal / np.max(np.abs(seasonal))
    return seasonal, z, doy


def holiday_terms(cfg, dates):
    h = cfg["baseline"]["holidays"]
    bump = np.zeros(len(dates))
    flag = np.zeros(len(dates), dtype=int)
    for year in range(dates[0].year, dates[-1].year + 1):
        for day, amp in (
            (black_friday(year), h["black_friday_bump"]),
            (pd.Timestamp(year, 12, 24), h["pre_christmas_bump"]),
        ):
            i = week_index(dates, day)
            if i is not None:
                bump[i] += amp
                flag[i] = 1
    return bump, flag


def build_promos(cfg, dates, rng):
    p = cfg["promos"]
    n = len(dates)
    flag = np.zeros(n, dtype=int)
    uplift = np.zeros(n)
    events = []
    for year in range(dates[0].year, dates[-1].year + 1):
        for ev in p["events"]:
            if ev["type"] == "nth_mondays":
                mondays = [
                    i for i, d in enumerate(dates) if d.year == year and d.month == ev["month"]
                ]
                wk = [mondays[k - 1] for k in ev["nths"] if k - 1 < len(mondays)]
            elif ev["type"] == "black_friday":
                i = week_index(dates, black_friday(year))
                wk = [i] if i is not None else []
            else:
                raise ValueError(f"unknown promo type: {ev['type']}")
            if not wk:
                continue
            u = float(rng.normal(p["uplift_mean"], p["uplift_sd"]))
            for w in wk:
                flag[w] = 1
                uplift[w] = u
            events.append(
                {"name": ev["name"], "year": year, "weeks": [int(w) for w in wk], "uplift": u}
            )
    ramp = np.zeros(n)
    ramp[flag == 1] = 1.0
    ant = cfg["budget_rules"]["anticipation_level"]
    for ev in events:
        before = ev["weeks"][0] - 1
        if before >= 0 and flag[before] == 0:
            ramp[before] = max(ramp[before], ant)
    return flag, uplift, ramp, events


# ------------------------------------------------------------------------- simulator
def simulate(cfg, seed, config_sha256=None, confounding=None):
    """Return (observed_df, truth_dict). Pure function of (cfg, seed, confounding)."""
    conf_on = cfg["confounding"]["enabled"] if confounding is None else bool(confounding)
    chans = cfg["channels"]
    keys = list(chans)

    names = (
        ["latent", "noise", "promo", "proxy"]
        + [f"price_{k}" for k in keys]
        + [f"plan_{k}" for k in keys]
    )
    seqs = np.random.SeedSequence(int(seed)).spawn(len(names))
    rngs = {nm: np.random.default_rng(s) for nm, s in zip(names, seqs, strict=True)}

    dates = build_calendar(cfg)
    n = len(dates)
    t_idx = np.arange(n)
    seasonal, Z, doy = seasonal_terms(cfg, dates)
    hol_bump, holiday_flag = holiday_terms(cfg, dates)
    promo_flag, promo_uplift_frac, ramp, events = build_promos(cfg, dates, rngs["promo"])

    # ---- baseline demand, latent shock, sales noise ----------------------------------
    b = cfg["baseline"]
    baseline = (
        b["start_level"] * (1 + b["trend_per_year"] * t_idx / 52.0) * (1 + seasonal + hol_bump)
    )
    log_d = ar1(rngs["latent"], n, b["latent_demand"]["rho"], b["latent_demand"]["sd"])
    d = np.exp(log_d)
    base_demand = baseline * d
    sales_noise = b["noise"]["sd_frac"] * baseline * ar1(rngs["noise"], n, b["noise"]["rho"], 1.0)
    promo_uplift = promo_flag * promo_uplift_frac * baseline

    # ---- Search demand mechanism (independent of spend, so vectorized) ----------------
    sd_cfg = cfg["search_demand"]
    vol_true = sd_cfg["query_volume_at_start"] * base_demand / b["start_level"]
    vol_obs = vol_true * np.exp(sd_cfg["proxy_noise_sd"] * rngs["proxy"].standard_normal(n))
    demand_clicks = sd_cfg["demand_click_share"] * vol_true

    # ---- per-channel precomputation -----------------------------------------------------
    rules = cfg["budget_rules"]
    pre = {}
    for k in keys:
        c = chans[k]
        bud = c["budget"]
        m_cal = np.maximum(
            rules["multiplier_floor"], 1 + bud["season_sens"] * Z + bud["promo_sens"] * ramp
        )
        norm = c["mean_spend"] / m_cal.mean()
        plan = mean_one_lognormal(rngs[f"plan_{k}"], n, bud["planning_noise_sd"])
        if c["exposure"] == "spend":
            price = np.ones(n)
            xbar = c["mean_spend"]
        else:
            pr = c["price"]
            u = ar1(rngs[f"price_{k}"], n, pr["ar_rho"], pr["log_sd"])
            price = pr["base"] * (1 + pr["q4_amp"] * np.maximum(Z, 0.0)) * np.exp(u)
            xbar = c["mean_spend"] / pr["base"]
        a = c["adstock"]
        w = carryover_weights(a["type"], a["decay"], a.get("peak_lag", 0))
        pre[k] = dict(
            m_cal=m_cal,
            norm=norm,
            plan=plan,
            price=price,
            xbar=xbar,
            w=w,
            chase=bud["chase"] if conf_on else 0.0,
            track=bud.get("latent_tracking", 0.0) if conf_on else 0.0,
        )

    spend = {k: np.zeros(n) for k in keys}
    expo = {k: np.zeros(n) for k in keys}
    ads = {k: np.zeros(n) for k in keys}
    contrib = {k: np.zeros(n) for k in keys}
    hist = {
        k: np.concatenate([np.full(ADSTOCK_LAGS - 1, pre[k]["xbar"]), np.zeros(n)]) for k in keys
    }
    sales = np.zeros(n)
    g_series = np.zeros(n)

    # ---- week-by-week loop (spend at t depends on sales at t-1) --------------------------
    ref_w = rules["chase_ref_weeks"]
    for t in range(n):
        if t >= ref_w + 1:
            ref = sales[t - ref_w - 1 : t - 1].mean()
            g = float(np.clip(sales[t - 1] / ref - 1.0, -rules["chase_clip"], rules["chase_clip"]))
        else:
            g = 0.0
        g_series[t] = g
        total_media = 0.0
        for k in keys:
            c, p = chans[k], pre[k]
            chase = max(rules["multiplier_floor"], 1 + p["chase"] * g)
            track = max(rules["multiplier_floor"], 1 + p["track"] * log_d[t])
            spend[k][t] = p["norm"] * p["m_cal"][t] * chase * track * p["plan"][t]
            expo[k][t] = spend[k][t] / p["price"][t]
            hist[k][ADSTOCK_LAGS - 1 + t] = expo[k][t]
            window = hist[k][t : t + ADSTOCK_LAGS][::-1]  # x_t, x_{t-1}, ...
            ads[k][t] = p["w"] @ window
            contrib[k][t] = c["beta"] * hill(
                ads[k][t], c["saturation"]["k"], c["saturation"]["shape"]
            )
            total_media += contrib[k][t]
        sales[t] = base_demand[t] + promo_uplift[t] + total_media + sales_noise[t]

    # ---- observed dataset ----------------------------------------------------------------
    doy_phase1 = 2 * np.pi * doy / 365.25
    obs = pd.DataFrame({"week_start": dates.strftime("%Y-%m-%d"), "t": t_idx, "sales": sales})
    for k in keys:
        obs[f"{k}_spend"] = spend[k]
        if chans[k]["exposure"] == "impressions":
            obs[f"{k}_impressions"] = expo[k]
        elif chans[k]["exposure"] == "clicks":
            extra = demand_clicks if k == sd_cfg["channel"] else 0.0
            obs[f"{k}_clicks"] = expo[k] + extra
    obs["organic_search_volume"] = vol_obs
    obs["promo_flag"] = promo_flag
    obs["holiday_flag"] = holiday_flag
    obs["fourier_sin1"] = np.sin(doy_phase1)
    obs["fourier_cos1"] = np.cos(doy_phase1)
    obs["fourier_sin2"] = np.sin(2 * doy_phase1)
    obs["fourier_cos2"] = np.cos(2 * doy_phase1)
    obs = obs.round(6)

    # ---- ground truth ----------------------------------------------------------------------
    sk = sd_cfg["channel"]
    weekly = {
        "true_baseline_before_shock": baseline,
        "true_latent_demand_shock": d,
        "true_promo_uplift": promo_uplift,
        "true_sales_noise": sales_noise,
        "true_seasonal_index_Z": Z,
        "true_query_volume": vol_true,
        "true_search_demand_clicks": demand_clicks,
        "true_search_incremental_clicks": expo[sk],
        "true_budget_performance_signal_g": g_series,
    }
    for k in keys:
        weekly[f"true_{k}_exposure"] = expo[k]
        weekly[f"true_{k}_price"] = pre[k]["price"]
        weekly[f"true_{k}_adstock"] = ads[k]
        weekly[f"true_{k}_contribution"] = contrib[k]

    design, realized = {}, {}
    total_sales = float(sales.sum())
    for k in keys:
        c = chans[k]
        a, s = c["adstock"], c["saturation"]
        mass = 1.0 / (1.0 - a["decay"])
        abar = pre[k]["xbar"] * mass
        price0 = 1.0 if c["exposure"] == "spend" else c["price"]["base"]
        design[k] = {
            "typical_week_avg_roas": float(
                c["beta"] * hill(abar, s["k"], s["shape"]) / c["mean_spend"]
            ),
            "typical_week_marginal_roas": float(
                hill_slope(abar, s["k"], s["shape"], c["beta"]) * mass / price0
            ),
        }
        realized[k] = {
            "mean_spend": float(spend[k].mean()),
            "total_contribution": float(contrib[k].sum()),
            "avg_roas": float(contrib[k].sum() / spend[k].sum()),
            "share_of_sales": float(contrib[k].sum() / total_sales),
            "corr_spend_vs_seasonal_index": corr(spend[k], Z),
            "corr_spend_vs_promo_flag": corr(spend[k], promo_flag),
            "corr_spend_vs_latent_shock": corr(spend[k], log_d),
            "corr_spend_vs_sales_noise": corr(spend[k], sales_noise),
        }
    realized["search_extras"] = {
        "share_of_observed_clicks_not_incremental": float(
            demand_clicks.sum() / (expo[sk] + demand_clicks).sum()
        ),
        "corr_observed_clicks_vs_true_query_volume": corr(expo[sk] + demand_clicks, vol_true),
        "corr_observed_volume_vs_true_query_volume": corr(vol_obs, vol_true),
    }
    realized["all_media_share_of_sales"] = float(sum(contrib[k].sum() for k in keys) / total_sales)

    truth = {
        "SYNTHETIC_DATA": True,
        "config_version": cfg["config_version"],
        "config_sha256": config_sha256,
        "seed": int(seed),
        "confounding_enabled": conf_on,
        "parameters": {
            "channels": chans,
            "baseline": cfg["baseline"],
            "promos": cfg["promos"],
            "budget_rules": cfg["budget_rules"],
            "search_demand": cfg["search_demand"],
        },
        "promo_events": events,
        "design_values_typical_week": design,
        "realized": realized,
        "weekly": {
            "week_start": list(obs["week_start"]),
            **{k: np.asarray(v) for k, v in weekly.items()},
        },
    }
    return obs, truth


# ------------------------------------------------------------------------------ checks
def self_check(obs, truth, cfg):
    n = int(cfg["calendar"]["n_weeks"])
    assert len(obs) == n, "wrong number of weeks"
    assert not obs.isna().any().any(), "NaN in observed data"
    assert (obs["sales"] > 0).all(), "non-positive sales"
    assert int(obs["promo_flag"].sum()) == cfg["promos"]["expected_promo_weeks"], (
        "promo week count drifted"
    )
    assert not any(c.startswith("true_") for c in obs.columns), (
        "leakage: hidden column in observed data"
    )
    for k in ("weekly",):
        for name, arr in truth[k].items():
            if name != "week_start":
                assert len(arr) == n and np.isfinite(arr).all(), f"bad truth column {name}"


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return [round(float(v), 6) for v in x]
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def main():
    ap = argparse.ArgumentParser(description="Generate SYNTHETIC weekly MMM data.")
    ap.add_argument("--config", default="config_v1.yaml")
    ap.add_argument(
        "--seed", type=int, default=None, help="defaults to seeds.primary in the config"
    )
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-confounding", action="store_true")
    args = ap.parse_args()

    cfg, sha = load_config(args.config)
    seed = cfg["seeds"]["primary"] if args.seed is None else args.seed
    obs, truth = simulate(
        cfg, seed, config_sha256=sha, confounding=False if args.no_confounding else None
    )
    self_check(obs, truth, cfg)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    obs.to_csv(out / "synthetic_mmm_data.csv", index=False)
    (out / "ground_truth.json").write_text(json.dumps(_jsonable(truth), indent=1))

    r, dsg = truth["realized"], truth["design_values_typical_week"]
    print(
        f"SYNTHETIC data | config v{cfg['config_version']} | seed {seed} | "
        f"confounding={truth['confounding_enabled']}"
    )
    print(
        f"{'channel':<16}{'mean spend':>11}{'ROAS design':>12}{'ROAS real.':>11}{'share sales':>12}"
        f"{'r(Z)':>7}{'r(logd)':>9}{'r(noise)':>10}"
    )
    for k in cfg["channels"]:
        print(
            f"{k:<16}{r[k]['mean_spend']:>11.1f}{dsg[k]['typical_week_avg_roas']:>12.2f}{r[k]['avg_roas']:>11.2f}"
            f"{r[k]['share_of_sales']:>12.3f}{r[k]['corr_spend_vs_seasonal_index']:>7.2f}"
            f"{r[k]['corr_spend_vs_latent_shock']:>9.2f}{r[k]['corr_spend_vs_sales_noise']:>10.2f}"
        )
    print(f"all media share of sales: {r['all_media_share_of_sales']:.3f}")
    not_incremental = r["search_extras"]["share_of_observed_clicks_not_incremental"]
    print(f"search clicks not incremental: {not_incremental:.3f}")


if __name__ == "__main__":
    main()
