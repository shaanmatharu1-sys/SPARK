#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "quant_stats.h"
#include "backtest.h"

namespace py = pybind11;
using namespace pybind11::literals;
using namespace quant;

PYBIND11_MODULE(quant_module, m) {
    m.doc() = "Quant analytics engine — rolling stats, signals, backtest (C++ via pybind11)";

    // ── Rolling statistics ────────────────────────────────────────────────────
    m.def("rolling_mean",   &rolling_mean,   "x"_a, "window"_a);
    m.def("rolling_std",    &rolling_std,    "x"_a, "window"_a);
    m.def("rolling_zscore", &rolling_zscore, "x"_a, "window"_a);
    m.def("ewma",           &ewma,           "x"_a, "span"_a);

    // ── Returns & vol ─────────────────────────────────────────────────────────
    m.def("simple_returns", &simple_returns, "price"_a);
    m.def("log_returns",    &log_returns,    "price"_a);
    m.def("realized_vol",   &realized_vol,   "returns"_a, "periods_per_year"_a = 252.0);
    m.def("rolling_realized_vol", &rolling_realized_vol,
          "returns"_a, "window"_a, "periods_per_year"_a = 252.0);

    // ── Mean reversion ────────────────────────────────────────────────────────
    m.def("ou_half_life",    &ou_half_life,    "x"_a);
    m.def("hurst_exponent",  &hurst_exponent,  "x"_a);

    // ── Cross-sectional ───────────────────────────────────────────────────────
    m.def("zscore",          &zscore,          "x"_a);
    m.def("rank_normalize",  &rank_normalize,  "x"_a);
    m.def("correlation",     &correlation,     "a"_a, "b"_a);
    m.def("beta",            &beta,            "asset_returns"_a, "benchmark_returns"_a);

    // ── Performance stats ─────────────────────────────────────────────────────
    py::class_<PerfStats>(m, "PerfStats")
        .def_readonly("total_return", &PerfStats::total_return)
        .def_readonly("ann_return",   &PerfStats::ann_return)
        .def_readonly("ann_vol",      &PerfStats::ann_vol)
        .def_readonly("sharpe",       &PerfStats::sharpe)
        .def_readonly("sortino",      &PerfStats::sortino)
        .def_readonly("max_drawdown", &PerfStats::max_drawdown)
        .def_readonly("calmar",       &PerfStats::calmar)
        .def_readonly("hit_rate",     &PerfStats::hit_rate)
        .def_readonly("avg_win",      &PerfStats::avg_win)
        .def_readonly("avg_loss",     &PerfStats::avg_loss)
        .def_readonly("profit_factor",&PerfStats::profit_factor)
        .def_readonly("n_trades",     &PerfStats::n_trades)
        .def("to_dict", [](const PerfStats& p) {
            return py::dict(
                "total_return"_a = p.total_return,
                "ann_return"_a   = p.ann_return,
                "ann_vol"_a      = p.ann_vol,
                "sharpe"_a       = p.sharpe,
                "sortino"_a      = p.sortino,
                "max_drawdown"_a = p.max_drawdown,
                "calmar"_a       = p.calmar,
                "hit_rate"_a     = p.hit_rate,
                "avg_win"_a      = p.avg_win,
                "avg_loss"_a     = p.avg_loss,
                "profit_factor"_a= p.profit_factor,
                "n_trades"_a     = p.n_trades
            );
        });

    m.def("perf_stats", &perf_stats,
          "strategy_returns"_a, "rf_rate"_a = 0.0, "periods_per_year"_a = 252.0);

    // ── Backtest ──────────────────────────────────────────────────────────────
    py::class_<BacktestResult>(m, "BacktestResult")
        .def_readonly("strategy_returns", &BacktestResult::strategy_returns)
        .def_readonly("equity_curve",     &BacktestResult::equity_curve)
        .def_readonly("gross_returns",    &BacktestResult::gross_returns)
        .def_readonly("total_turnover",   &BacktestResult::total_turnover)
        .def_readonly("stats",            &BacktestResult::stats);

    m.def("backtest_signal", &backtest_signal,
          "prices"_a, "positions"_a, "cost_bps"_a = 1.0, "ppy"_a = 252.0);

    m.def("backtest_cross_sectional", &backtest_cross_sectional,
          "returns_matrix"_a, "scores_matrix"_a,
          "top_pct"_a = 0.2, "cost_bps"_a = 1.0, "ppy"_a = 252.0);
}
