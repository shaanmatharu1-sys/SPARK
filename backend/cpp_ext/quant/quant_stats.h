#pragma once
#include <vector>
#include <cstddef>
#include <utility>

namespace quant {

using Vec = std::vector<double>;

// ── Rolling statistics ───────────────────────────────────────────────────────

/** Rolling mean over a trailing window. Returns vector same length as input;
 *  first (window-1) entries are NaN. */
Vec rolling_mean(const Vec& x, std::size_t window);

/** Rolling standard deviation (sample, ddof=1). */
Vec rolling_std(const Vec& x, std::size_t window);

/** Rolling z-score: (x[t] - rolling_mean) / rolling_std. */
Vec rolling_zscore(const Vec& x, std::size_t window);

/** Exponentially-weighted moving average with given span. */
Vec ewma(const Vec& x, double span);

// ── Returns & volatility ─────────────────────────────────────────────────────

/** Simple returns: x[t]/x[t-1] - 1. Length n-1. */
Vec simple_returns(const Vec& price);

/** Log returns: ln(x[t]/x[t-1]). Length n-1. */
Vec log_returns(const Vec& price);

/** Annualized realized volatility from a return series. */
double realized_vol(const Vec& returns, double periods_per_year = 252.0);

/** Rolling annualized realized vol. */
Vec rolling_realized_vol(const Vec& returns, std::size_t window,
                         double periods_per_year = 252.0);

// ── Mean reversion ───────────────────────────────────────────────────────────

/** Ornstein-Uhlenbeck half-life of mean reversion, estimated by regressing
 *  Δx[t] on x[t-1]. Returns half-life in periods; <=0 means non-mean-reverting. */
double ou_half_life(const Vec& x);

/** Hurst exponent via rescaled-range (R/S) analysis.
 *  <0.5 mean-reverting, =0.5 random walk, >0.5 trending. */
double hurst_exponent(const Vec& x);

// ── Cross-sectional ──────────────────────────────────────────────────────────

/** Cross-sectional z-score of a single vector (across names at one point). */
Vec zscore(const Vec& x);

/** Cross-sectional rank in [0,1] (ties -> average rank). */
Vec rank_normalize(const Vec& x);

/** Pearson correlation between two equal-length series. */
double correlation(const Vec& a, const Vec& b);

/** Beta of a vs b (cov(a,b)/var(b)) — e.g. asset vs benchmark returns. */
double beta(const Vec& asset_returns, const Vec& benchmark_returns);

// ── Performance stats (for backtest) ─────────────────────────────────────────

struct PerfStats {
    double total_return;
    double ann_return;
    double ann_vol;
    double sharpe;
    double sortino;
    double max_drawdown;
    double calmar;
    double hit_rate;
    double avg_win;
    double avg_loss;
    double profit_factor;
    int    n_trades;
};

/** Compute full performance stats from a per-period strategy return series. */
PerfStats perf_stats(const Vec& strategy_returns, double rf_rate = 0.0,
                     double periods_per_year = 252.0);

// ── Pairs trading / cointegration ────────────────────────────────────────────

struct PairResult {
    double hedge_ratio;     // beta from regressing y on x (OLS slope)
    double intercept;       // OLS intercept
    double correlation;     // price correlation
    double adf_stat;        // Augmented Dickey-Fuller test statistic on spread
    double half_life;       // OU half-life of the spread (periods)
    double spread_z;        // current spread z-score
    double spread_mean;     // mean of spread
    double spread_std;      // std of spread
    bool   is_cointegrated; // adf_stat < critical value (~ -2.86 at 5%)
};

/** Test a pair (y, x) for cointegration. Regresses y on x, then runs an
 *  ADF-style stationarity test on the residual spread, plus half-life and
 *  current z-score. Both series must be equal length, price levels. */
PairResult test_pair(const Vec& y, const Vec& x);

/** Simple OLS slope+intercept of y on x. Returns {slope, intercept}. */
std::pair<double,double> ols(const Vec& y, const Vec& x);

} // namespace quant

