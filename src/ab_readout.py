"""
ab_readout.py
A reusable A/B test readout for a binary (converted yes/no) metric.

One function call runs the full checklist:
  1. Sample ratio mismatch (SRM) check  -> is the test valid to read at all?
  2. Conversion by group, difference, relative lift
  3. Two-proportion z-test and 95% confidence interval
  4. Power: the minimum detectable effect (MDE) this test could catch
  5. Bayesian readout: P(treatment better) and expected loss of each choice
  6. Optional £ impact per year
  7. A plain-English recommendation

Example
-------
    import pandas as pd
    from src.ab_readout import ab_readout

    df = pd.read_csv("data/clean/ab_clean.csv")
    result = ab_readout(df, group_col="group", metric_col="converted",
                        control="control", treatment="treatment",
                        value_per_conversion=50, annual_users=4_600_000)
"""

import numpy as np
from scipy.stats import chisquare, norm
from statsmodels.stats.power import NormalIndPower


def ab_readout(df, group_col, metric_col, control, treatment,
               expected_split=0.5, alpha=0.05, power=0.8,
               value_per_conversion=None, annual_users=None,
               n_draws=200_000, seed=42, verbose=True):
    """Run a full A/B test readout and return the results as a dictionary."""

    # ---- 1. Counts and SRM check ------------------------------------------
    d = df[df[group_col].isin([control, treatment])]
    n_c = int((d[group_col] == control).sum())
    n_t = int((d[group_col] == treatment).sum())
    x_c = int(d.loc[d[group_col] == control, metric_col].sum())
    x_t = int(d.loc[d[group_col] == treatment, metric_col].sum())
    total = n_c + n_t

    expected = [total * (1 - expected_split), total * expected_split]
    srm_p = chisquare([n_c, n_t], expected)[1]
    srm_ok = srm_p >= 0.001

    # ---- 2. Rates and lift --------------------------------------------------
    p_c, p_t = x_c / n_c, x_t / n_t
    diff = p_t - p_c
    rel_lift = diff / p_c if p_c > 0 else np.nan

    # ---- 3. Two-proportion z-test and confidence interval -----------------
    pool = (x_c + x_t) / total
    se_pool = np.sqrt(pool * (1 - pool) * (1 / n_c + 1 / n_t))
    z = diff / se_pool
    p_value = 2 * (1 - norm.cdf(abs(z)))

    se = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z_crit = norm.ppf(1 - alpha / 2)
    ci_low, ci_high = diff - z_crit * se, diff + z_crit * se

    # ---- 4. Power: minimum detectable effect --------------------------------
    h = NormalIndPower().solve_power(nobs1=n_c, alpha=alpha, power=power, ratio=n_t / n_c)
    mde_rate = np.sin(np.arcsin(np.sqrt(p_c)) + h / 2) ** 2
    mde_abs = mde_rate - p_c
    mde_rel = mde_abs / p_c

    # ---- 5. Bayesian readout (flat Beta(1,1) priors) ------------------------
    rng = np.random.default_rng(seed)
    post_c = rng.beta(1 + x_c, 1 + n_c - x_c, n_draws)
    post_t = rng.beta(1 + x_t, 1 + n_t - x_t, n_draws)
    draws = post_t - post_c
    prob_t_better = (draws > 0).mean()
    loss_ship = np.maximum(-draws, 0).mean()
    loss_keep = np.maximum(draws, 0).mean()

    # ---- 6. Optional £ impact ---------------------------------------------
    money = None
    if value_per_conversion is not None and annual_users is not None:
        k = annual_users * value_per_conversion
        money = {
            "expected_per_year": draws.mean() * k,
            "worst_case_2.5pct": np.percentile(draws, 2.5) * k,
            "best_case_97.5pct": np.percentile(draws, 97.5) * k,
            "regret_if_ship": loss_ship * k,
            "regret_if_keep": loss_keep * k,
        }

    # ---- 7. Recommendation -------------------------------------------------
    if not srm_ok:
        decision = "INVALID - sample ratio mismatch. Fix the assignment bug before reading any result."
    elif ci_low > 0:
        decision = "SHIP - treatment is better and the whole confidence interval is above zero."
    elif ci_high < 0:
        decision = "DO NOT SHIP - treatment is worse and the whole confidence interval is below zero."
    elif loss_ship > loss_keep:
        decision = (f"KEEP CONTROL - no significant difference, and shipping carries more risk "
                    f"({loss_ship*10000:.1f} vs {loss_keep*10000:.1f} conversions lost per 10k users). "
                    f"This test could detect lifts of {mde_rel*100:.1f}% or more.")
    else:
        decision = (f"NO CLEAR WINNER - treatment is slightly favoured but not significant. "
                    f"This test could only detect lifts of {mde_rel*100:.1f}% or more; consider a larger test.")

    result = {
        "users_control": n_c, "users_treatment": n_t,
        "srm_p_value": srm_p, "srm_ok": srm_ok,
        "rate_control": p_c, "rate_treatment": p_t,
        "diff_pp": diff * 100, "relative_lift_pct": rel_lift * 100,
        "ci_low_pp": ci_low * 100, "ci_high_pp": ci_high * 100,
        "z": z, "p_value": p_value,
        "mde_pp": mde_abs * 100, "mde_relative_pct": mde_rel * 100,
        "prob_treatment_better": prob_t_better,
        "expected_loss_ship_per_10k": loss_ship * 10000,
        "expected_loss_keep_per_10k": loss_keep * 10000,
        "money": money,
        "decision": decision,
    }

    if verbose:
        _print_readout(result, alpha)
    return result


def _print_readout(r, alpha):
    line = "-" * 62
    print(line)
    print("A/B TEST READOUT")
    print(line)
    print(f"1. Sample ratio   control {r['users_control']:,} | treatment {r['users_treatment']:,}"
          f" | SRM p = {r['srm_p_value']:.4f} {'OK' if r['srm_ok'] else 'ALARM'}")
    print(f"2. Conversion     control {r['rate_control']*100:.3f}% | treatment {r['rate_treatment']*100:.3f}%")
    print(f"   Difference     {r['diff_pp']:+.3f} pp ({r['relative_lift_pct']:+.2f}% relative)")
    print(f"3. Frequentist    {int((1-alpha)*100)}% CI {r['ci_low_pp']:+.3f} to {r['ci_high_pp']:+.3f} pp"
          f" | z = {r['z']:.2f} | p = {r['p_value']:.4f}")
    print(f"4. Power          MDE {r['mde_pp']:.3f} pp ({r['mde_relative_pct']:.2f}% relative) at 80% power")
    print(f"5. Bayesian       P(treatment better) = {r['prob_treatment_better']*100:.1f}%")
    print(f"                  expected loss per 10k users: ship {r['expected_loss_ship_per_10k']:.1f}"
          f" | keep {r['expected_loss_keep_per_10k']:.1f}")
    if r["money"]:
        m = r["money"]
        print(f"6. £ per year     expected {m['expected_per_year']:+,.0f} | range {m['worst_case_2.5pct']:+,.0f}"
              f" to {m['best_case_97.5pct']:+,.0f}")
        print(f"                  regret: ship £{m['regret_if_ship']:,.0f} | keep £{m['regret_if_keep']:,.0f}")
    print(line)
    print("DECISION:", r["decision"])
    print(line)
