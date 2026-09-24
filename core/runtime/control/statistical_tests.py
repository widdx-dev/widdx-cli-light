"""Statistical Significance Testing for Counterfactual Experiments.

Provides real statistical tests to determine if A/B experiment results
are significant or due to chance.

Tests implemented:
  1. Two-proportion z-test — for success rates (binary outcomes)
  2. Welch's t-test — for continuous outcomes (cost, steps, latency)
  3. Chi-square test — for categorical outcomes (escalation, abort counts)
  4. Effect size (Cohen's d) — practical significance, not just statistical

All tests return p-values with standard significance thresholds:
  - p < 0.05: statistically significant
  - p < 0.01: highly significant
  - p < 0.001: very highly significant
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("widdx.stats")


@dataclass
class StatisticalTestResult:
    """Result of a statistical significance test."""
    test_name: str
    statistic: float  # z-value, t-value, or chi-square value
    p_value: float  # probability of observing this result by chance
    is_significant: bool  # p < 0.05
    effect_size: float  # Cohen's d or similar
    effect_interpretation: str  # "negligible", "small", "medium", "large"
    recommendation: str


def _normal_cdf(x: float) -> float:
    """Approximation of the standard normal CDF using error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _inverse_normal_cdf(p: float) -> float:
    """Approximation of the inverse normal CDF (probit function)."""
    if p <= 0 or p >= 1:
        return 0.0
    # Rational approximation for the probit function
    # Abramowitz and Stegun approximation
    if p < 0.5:
        return -_inverse_normal_cdf(1.0 - p)
    # p >= 0.5
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    # Rational approximation coefficients
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def _gamma_ln(x: float) -> float:
    """Log of gamma function using Lanczos approximation."""
    if x <= 0:
        return 0.0
    coefs = [
        76.18009172947146, -86.50532032941677, 24.01409824083091,
        -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5
    ]
    y = x
    tmp = x + 5.5
    tmp -= (x - 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in coefs:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def _beta_ln(x: float, y: float) -> float:
    """Log of beta function."""
    return _gamma_ln(x) + _gamma_ln(y) - _gamma_ln(x + y)


def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function using continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Continued fraction evaluation
    max_iter = 200
    eps = 1e-10
    # Lentz's algorithm
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        # Even step
        m2 = 2 * m
        aa = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        # Odd step
        aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    # Front factor
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - _beta_ln(a, b))
    return front * h / a


def _student_t_cdf(t: float, df: float) -> float:
    """CDF of Student's t-distribution using incomplete beta function."""
    if df <= 0:
        return 0.0
    x = df / (df + t * t)
    ib = _incomplete_beta(df / 2.0, 0.5, x)
    if t >= 0:
        return 1.0 - 0.5 * ib
    else:
        return 0.5 * ib


def two_proportion_z_test(
    successes_a: int, trials_a: int,
    successes_b: int, trials_b: int,
    alpha: float = 0.05
) -> StatisticalTestResult:
    """Two-proportion z-test for comparing success rates.

    Tests whether the proportion of successes in group A is significantly
    different from group B.

    Args:
        successes_a: number of successes in group A (baseline)
        trials_a: total trials in group A
        successes_b: number of successes in group B (candidate)
        trials_b: total trials in group B
        alpha: significance level (default 0.05)

    Returns:
        StatisticalTestResult with z-statistic, p-value, and interpretation
    """
    if trials_a < 5 or trials_b < 5:
        return StatisticalTestResult(
            test_name="Two-proportion z-test",
            statistic=0.0, p_value=1.0, is_significant=False,
            effect_size=0.0, effect_interpretation="insufficient_data",
            recommendation="Need at least 5 trials per group"
        )

    p_a = successes_a / trials_a
    p_b = successes_b / trials_b
    p_pool = (successes_a + successes_b) / (trials_a + trials_b)

    # Standard error under null hypothesis
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / trials_a + 1.0 / trials_b))
    if se < 1e-10:
        se = 1e-10

    z = (p_b - p_a) / se
    # Two-tailed p-value
    p_value = 2.0 * (1.0 - _normal_cdf(abs(z)))

    # Effect size: Cohen's h (arcsin transformation)
    h = 2.0 * (math.asin(math.sqrt(p_b)) - math.asin(math.sqrt(p_a)))
    effect_abs = abs(h)
    if effect_abs < 0.2:
        effect_interp = "negligible"
    elif effect_abs < 0.5:
        effect_interp = "small"
    elif effect_abs < 0.8:
        effect_interp = "medium"
    else:
        effect_interp = "large"

    is_sig = p_value < alpha
    if is_sig:
        direction = "better" if p_b > p_a else "worse"
        rec = f"Candidate is significantly {direction} (p={p_value:.4f}, h={h:.3f})"
    else:
        rec = f"No significant difference (p={p_value:.4f}). Continue experiment."

    return StatisticalTestResult(
        test_name="Two-proportion z-test",
        statistic=round(z, 4),
        p_value=round(p_value, 6),
        is_significant=is_sig,
        effect_size=round(h, 4),
        effect_interpretation=effect_interp,
        recommendation=rec,
    )


def welch_t_test(
    mean_a: float, var_a: float, n_a: int,
    mean_b: float, var_b: float, n_b: int,
    alpha: float = 0.05
) -> StatisticalTestResult:
    """Welch's t-test for comparing means of two independent samples.

    Does NOT assume equal variances — more robust than Student's t-test.

    Args:
        mean_a, var_a, n_a: mean, variance, sample size for group A
        mean_b, var_b, n_b: mean, variance, sample size for group B
        alpha: significance level

    Returns:
        StatisticalTestResult with t-statistic, p-value, and Cohen's d
    """
    if n_a < 3 or n_b < 3:
        return StatisticalTestResult(
            test_name="Welch's t-test",
            statistic=0.0, p_value=1.0, is_significant=False,
            effect_size=0.0, effect_interpretation="insufficient_data",
            recommendation="Need at least 3 samples per group"
        )

    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se < 1e-10:
        se = 1e-10

    t = (mean_b - mean_a) / se

    # Welch-Satterthwaite degrees of freedom
    num = (var_a / n_a + var_b / n_b) ** 2
    denom = ((var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1))
    if denom < 1e-10:
        denom = 1e-10
    df = num / denom

    # Two-tailed p-value
    p_value = 2.0 * (1.0 - _student_t_cdf(abs(t), df))

    # Effect size: Cohen's d (pooled standard deviation)
    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_sd < 1e-10:
        pooled_sd = 1e-10
    d = (mean_b - mean_a) / pooled_sd
    effect_abs = abs(d)
    if effect_abs < 0.2:
        effect_interp = "negligible"
    elif effect_abs < 0.5:
        effect_interp = "small"
    elif effect_abs < 0.8:
        effect_interp = "medium"
    else:
        effect_interp = "large"

    is_sig = p_value < alpha
    if is_sig:
        direction = "lower" if mean_b < mean_a else "higher"
        rec = f"Candidate is significantly {direction} (p={p_value:.4f}, d={d:.3f})"
    else:
        rec = f"No significant difference (p={p_value:.4f}). Continue experiment."

    return StatisticalTestResult(
        test_name="Welch's t-test",
        statistic=round(t, 4),
        p_value=round(p_value, 6),
        is_significant=is_sig,
        effect_size=round(d, 4),
        effect_interpretation=effect_interp,
        recommendation=rec,
    )


def chi_square_test(
    count_a_success: int, count_a_failure: int,
    count_b_success: int, count_b_failure: int,
    alpha: float = 0.05
) -> StatisticalTestResult:
    """Chi-square test of independence for 2x2 contingency table.

    Tests whether the success/failure distribution differs between groups.

    Args:
        count_a_success, count_a_failure: successes and failures in group A
        count_b_success, count_b_failure: successes and failures in group B
        alpha: significance level

    Returns:
        StatisticalTestResult with chi-square statistic and p-value
    """
    total = count_a_success + count_a_failure + count_b_success + count_b_failure
    if total < 20:
        return StatisticalTestResult(
            test_name="Chi-square test",
            statistic=0.0, p_value=1.0, is_significant=False,
            effect_size=0.0, effect_interpretation="insufficient_data",
            recommendation="Need at least 20 total observations"
        )

    # Contingency table
    row1 = count_a_success + count_a_failure  # total A
    row2 = count_b_success + count_b_failure  # total B
    col1 = count_a_success + count_b_success  # total success
    col2 = count_a_failure + count_b_failure  # total failure

    # Expected frequencies
    e_a_s = row1 * col1 / total
    e_a_f = row1 * col2 / total
    e_b_s = row2 * col1 / total
    e_b_f = row2 * col2 / total

    # Chi-square statistic
    chi2 = 0.0
    for obs, exp in [(count_a_success, e_a_s), (count_a_failure, e_a_f),
                     (count_b_success, e_b_s), (count_b_failure, e_b_f)]:
        if exp > 0:
            chi2 += (obs - exp) ** 2 / exp

    # p-value from chi-square distribution with 1 df
    # Using the fact that chi-square(1) = z^2
    p_value = 1.0 - _normal_cdf(math.sqrt(chi2))

    # Effect size: Cramér's V (for 2x2 table)
    v = math.sqrt(chi2 / total)
    effect_abs = v
    if effect_abs < 0.1:
        effect_interp = "negligible"
    elif effect_abs < 0.3:
        effect_interp = "small"
    elif effect_abs < 0.5:
        effect_interp = "medium"
    else:
        effect_interp = "large"

    is_sig = p_value < alpha
    if is_sig:
        rec = f"Significant association (p={p_value:.4f}, V={v:.3f})"
    else:
        rec = f"No significant association (p={p_value:.4f}). Continue experiment."

    return StatisticalTestResult(
        test_name="Chi-square test",
        statistic=round(chi2, 4),
        p_value=round(p_value, 6),
        is_significant=is_sig,
        effect_size=round(v, 4),
        effect_interpretation=effect_interp,
        recommendation=rec,
    )


def analyze_experiment(
    baseline_successes: int, baseline_trials: int,
    candidate_successes: int, candidate_trials: int,
    baseline_costs: list[float] | None = None,
    candidate_costs: list[float] | None = None,
    baseline_steps: list[float] | None = None,
    candidate_steps: list[float] | None = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Full statistical analysis of an A/B experiment.

    Runs multiple tests and aggregates results into a comprehensive report.

    Returns:
        dict with:
          - success_test: StatisticalTestResult for success rate
          - cost_test: StatisticalTestResult for cost (if data provided)
          - steps_test: StatisticalTestResult for steps (if data provided)
          - overall_significant: bool — True if any test is significant
          - recommendation: str — actionable conclusion
    """
    results: dict[str, Any] = {}

    # 1. Success rate test (proportion z-test)
    success_test = two_proportion_z_test(
        baseline_successes, baseline_trials,
        candidate_successes, candidate_trials,
        alpha=alpha,
    )
    results["success_test"] = success_test

    # 2. Cost test (Welch's t-test) — lower is better
    if baseline_costs and candidate_costs and len(baseline_costs) >= 3 and len(candidate_costs) >= 3:
        mean_a = sum(baseline_costs) / len(baseline_costs)
        var_a = sum((x - mean_a) ** 2 for x in baseline_costs) / (len(baseline_costs) - 1)
        mean_b = sum(candidate_costs) / len(candidate_costs)
        var_b = sum((x - mean_b) ** 2 for x in candidate_costs) / (len(candidate_costs) - 1)
        cost_test = welch_t_test(mean_a, var_a, len(baseline_costs), mean_b, var_b, len(candidate_costs), alpha)
        results["cost_test"] = cost_test

    # 3. Steps test (Welch's t-test) — lower is better
    if baseline_steps and candidate_steps and len(baseline_steps) >= 3 and len(candidate_steps) >= 3:
        mean_a = sum(baseline_steps) / len(baseline_steps)
        var_a = sum((x - mean_a) ** 2 for x in baseline_steps) / (len(baseline_steps) - 1)
        mean_b = sum(candidate_steps) / len(candidate_steps)
        var_b = sum((x - mean_b) ** 2 for x in candidate_steps) / (len(candidate_steps) - 1)
        steps_test = welch_t_test(mean_a, var_a, len(baseline_steps), mean_b, var_b, len(candidate_steps), alpha)
        results["steps_test"] = steps_test

    # 4. Overall assessment
    # For success: positive effect = candidate better
    # For cost/steps: negative effect = candidate better (lower is better)
    tests = [success_test]
    if "cost_test" in results:
        tests.append(results["cost_test"])
    if "steps_test" in results:
        tests.append(results["steps_test"])

    sig_tests = [t for t in tests if t.is_significant]

    # Count where candidate is better (considering direction)
    candidate_better_count = 0
    candidate_worse_count = 0
    for t in sig_tests:
        if t.test_name == "Two-proportion z-test":
            # Higher success = better
            if t.effect_size > 0:
                candidate_better_count += 1
            else:
                candidate_worse_count += 1
        else:
            # For cost/steps: negative effect size = lower = better
            if t.effect_size < 0:
                candidate_better_count += 1
            else:
                candidate_worse_count += 1

    if len(sig_tests) >= 2 and candidate_better_count > candidate_worse_count:
        overall = "ACCEPT"
        rec = f"Candidate wins on {candidate_better_count}/{len(sig_tests)} significant metrics"
    elif len(sig_tests) >= 2 and candidate_worse_count > candidate_better_count:
        overall = "REJECT"
        rec = f"Candidate loses on {candidate_worse_count}/{len(sig_tests)} significant metrics"
    elif len(sig_tests) == 1:
        overall = "INCONCLUSIVE"
        rec = "Only 1 significant metric. Need more data."
    else:
        overall = "INCONCLUSIVE"
        rec = f"No significant differences found (all p > {alpha})"

    results["overall_significant"] = len(sig_tests) >= 2
    results["overall_verdict"] = overall
    results["recommendation"] = rec
    results["alpha"] = alpha

    return results
