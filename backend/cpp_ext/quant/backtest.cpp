#include "backtest.h"
#include <cmath>
#include <algorithm>
#include <numeric>

namespace quant {

BacktestResult backtest_signal(const Vec& prices, const Vec& positions,
                               double cost_bps, double ppy) {
    BacktestResult res;
    std::size_t n = std::min(prices.size(), positions.size());
    if (n < 2) return res;

    Vec rets = simple_returns(prices);          // length n-1
    double cost = cost_bps / 10000.0;

    res.strategy_returns.reserve(n - 1);
    res.gross_returns.reserve(n - 1);
    res.equity_curve.reserve(n);
    res.equity_curve.push_back(1.0);

    double prev_pos = 0.0;
    double total_turnover = 0.0;
    double eq = 1.0;

    for (std::size_t t = 1; t < n; ++t) {
        // Position held into period t was decided at t-1
        double pos = positions[t - 1];
        double gross = pos * rets[t - 1];

        // Turnover cost when position changes
        double turnover = std::fabs(pos - prev_pos);
        double net = gross - turnover * cost;
        total_turnover += turnover;
        prev_pos = pos;

        res.gross_returns.push_back(gross);
        res.strategy_returns.push_back(net);
        eq *= (1.0 + net);
        res.equity_curve.push_back(eq);
    }

    res.total_turnover = total_turnover;
    res.stats = perf_stats(res.strategy_returns, 0.0, ppy);
    return res;
}

BacktestResult backtest_cross_sectional(const std::vector<Vec>& returns_matrix,
                                        const std::vector<Vec>& scores_matrix,
                                        double top_pct, double cost_bps, double ppy) {
    BacktestResult res;
    std::size_t n_periods = std::min(returns_matrix.size(), scores_matrix.size());
    if (n_periods < 2) return res;

    double cost = cost_bps / 10000.0;
    Vec prev_weights;
    double total_turnover = 0.0;
    double eq = 1.0;
    res.equity_curve.push_back(1.0);

    for (std::size_t t = 0; t < n_periods; ++t) {
        const Vec& scores = scores_matrix[t];
        const Vec& rets   = returns_matrix[t];
        std::size_t n_assets = std::min(scores.size(), rets.size());
        if (n_assets == 0) { res.strategy_returns.push_back(0.0); continue; }

        // Rank assets by score
        std::vector<std::size_t> idx(n_assets);
        std::iota(idx.begin(), idx.end(), 0);
        std::sort(idx.begin(), idx.end(),
                  [&](std::size_t a, std::size_t b){ return scores[a] > scores[b]; });

        std::size_t k = std::max((std::size_t)1, (std::size_t)(n_assets * top_pct));

        // Equal-weight long top-k, short bottom-k
        Vec weights(n_assets, 0.0);
        for (std::size_t i = 0; i < k; ++i) {
            weights[idx[i]]               =  0.5 / k;   // long
            weights[idx[n_assets-1-i]]    = -0.5 / k;   // short
        }

        // Period return = sum(weight * return)
        double gross = 0.0;
        for (std::size_t i = 0; i < n_assets; ++i) gross += weights[i] * rets[i];

        // Turnover vs previous weights
        double turnover = 0.0;
        if (!prev_weights.empty()) {
            for (std::size_t i = 0; i < n_assets; ++i) {
                double pw = i < prev_weights.size() ? prev_weights[i] : 0.0;
                turnover += std::fabs(weights[i] - pw);
            }
        } else {
            for (double w : weights) turnover += std::fabs(w);
        }

        double net = gross - turnover * cost;
        total_turnover += turnover;
        prev_weights = weights;

        res.gross_returns.push_back(gross);
        res.strategy_returns.push_back(net);
        eq *= (1.0 + net);
        res.equity_curve.push_back(eq);
    }

    res.total_turnover = total_turnover;
    res.stats = perf_stats(res.strategy_returns, 0.0, ppy);
    return res;
}

} // namespace quant
