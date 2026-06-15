#pragma once
#include <vector>
#include "quant_stats.h"

namespace quant {

/**
 * Vectorized signal backtest.
 *
 * Given a price series and a target-position series (e.g. signal in [-1, 1]),
 * simulates a strategy with transaction costs and returns per-period strategy
 * returns plus full performance stats.
 *
 * @param prices       close prices, length n
 * @param positions    target position per period, length n (same index as prices).
 *                     position[t] is the position held going INTO period t+1.
 * @param cost_bps     round-trip transaction cost in basis points per unit turnover
 * @param ppy          periods per year (252 daily, 252*390 minute, etc.)
 */
struct BacktestResult {
    Vec       strategy_returns;   // per-period net returns
    Vec       equity_curve;       // cumulative equity (starts at 1.0)
    Vec       gross_returns;      // before costs
    double    total_turnover;
    PerfStats stats;
};

BacktestResult backtest_signal(
    const Vec& prices,
    const Vec& positions,
    double cost_bps = 1.0,
    double ppy = 252.0
);

/**
 * Cross-sectional long/short backtest.
 *
 * @param returns_matrix  [n_periods][n_assets] forward returns
 * @param scores_matrix   [n_periods][n_assets] signal scores (higher = long)
 * @param top_pct         fraction of universe to go long (and short) e.g. 0.2
 * @param cost_bps        transaction cost per unit turnover
 * @param ppy             periods per year
 */
BacktestResult backtest_cross_sectional(
    const std::vector<Vec>& returns_matrix,
    const std::vector<Vec>& scores_matrix,
    double top_pct = 0.2,
    double cost_bps = 1.0,
    double ppy = 252.0
);

} // namespace quant
