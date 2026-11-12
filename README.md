# MMM Ground Truth

> **[TODO: one sentence that states the finding, e.g. "Paid search drove most of the incremental revenue, but only up to about X spend."]**
>
> Business question: Synthetic weekly MMM data with known ground truth, endogenous spend and a Search-clicks bias. Test your model against the answer.

![Key result](reports/figures/hero.png)
*[TODO: replace with your best chart. Title it with the takeaway, highlight one thing, add a source line.]*

## Why this matters

[TODO: 2-3 sentences. Who would make a decision from this, and what decision?]

## What I did

1. **Data:** [TODO: source, period, granularity. State clearly if it is synthetic.]
2. **Method:** [TODO: model or design, in plain language, with the key term explained in one clause.]
3. **Validation:** [TODO: how you checked it, e.g. holdout, refutation tests, parameter recovery.]

## Key findings

| Finding | Evidence | Confidence |
|---|---|---|
| [TODO] | [TODO] | [TODO: how sure, and why] |

## What this analysis can and cannot claim

Use this section to protect your credibility. A reader should never have to guess how far the evidence goes.

- **Can claim:** [TODO: e.g. "Within this model and these priors, channel A's estimated contribution is X, with a 94% credible interval of Y to Z."]
- **Cannot claim:** [TODO: e.g. "That the channel *caused* the lift outside the modeled period, because there is no randomized test behind it."]
- **Assumptions:** see [`docs/decisions.md`](docs/decisions.md).

## Reproduce it

```bash
git clone [TODO: repo URL]
cd mmm-ground-truth
uv sync                      # installs Python 3.13 and the exact dependencies
uv run pre-commit install    # blocks accidental data commits
uv run jupyter lab           # open notebooks/ and run in order
```

Data: this repository contains only synthetic or sample data in `data/sample/`. [TODO: say how the sample was generated.]

## Project structure

```
├── configs/        <- Simulation settings (true effects, spend rules, bias)
├── data/
│   ├── raw/        <- Original, immutable data (never edited)
│   ├── external/   <- Third-party data
│   ├── interim/    <- Intermediate transformations
│   └── processed/  <- Final datasets used for analysis
├── docs/           <- Decision log, assumptions, brief
├── notebooks/      <- Numbered, in order: 01-eda, 02-analysis, ...
├── reports/figures/<- Charts for the report and README
├── src/mmm_ground_truth/ <- Reusable code
└── tests/          <- Tests for src code
```


## Limitations and next steps

- [TODO: the biggest limitation, stated plainly]
- [TODO: what you would do next with more data or time]

## About

Built by **Mabelly Tuchsznajder**, Marketing Data Scientist, [All Else Equal Analytics](https://allelseequal.com).
*Isolating what really moves your marketing.*

[LinkedIn](https://www.linkedin.com/in/motsci) · mabelly@allelseequal.com

License: [MIT](LICENSE)
