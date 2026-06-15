#include "quant_stats.h"
#include <cmath>
#include <algorithm>
#include <numeric>
#include <limits>

namespace quant {

static const double NaN = std::numeric_limits<double>::quiet_NaN();

// ── Rolling statistics ───────────────────────────────────────────────────────

Vec rolling_mean(const Vec& x, std::size_t window) {
    std::size_t n = x.size();
    Vec out(n, NaN);
    if (window == 0 || window > n) return out;

    double sum = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        sum += x[i];
        if (i >= window) sum -= x[i - window];
        if (i >= window - 1) out[i] = sum / window;
    }
    return out;
}

Vec rolling_std(const Vec& x, std::size_t window) {
    std::size_t n = x.size();
    Vec out(n, NaN);
    if (window < 2 || window > n) return out;

    double sum = 0.0, sumsq = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        sum += x[i]; sumsq += x[i] * x[i];
        if (i >= window) {
            sum   -= x[i - window];
            sumsq -= x[i - window] * x[i - window];
        }
        if (i >= window - 1) {
            double mean = sum / window;
            double var  = (sumsq - window * mean * mean) / (window - 1);
            out[i] = var > 0.0 ? std::sqrt(var) : 0.0;
        }
    }
    return out;
}

Vec rolling_zscore(const Vec& x, std::size_t window) {
    std::size_t n = x.size();
    Vec m = rolling_mean(x, window);
    Vec s = rolling_std(x, window);
    Vec out(n, NaN);
    for (std::size_t i = 0; i < n; ++i) {
        if (!std::isnan(m[i]) && !std::isnan(s[i]) && s[i] > 0.0)
            out[i] = (x[i] - m[i]) / s[i];
    }
    return out;
}

Vec ewma(const Vec& x, double span) {
    std::size_t n = x.size();
    Vec out(n, NaN);
    if (n == 0 || span <= 0) return out;
    double alpha = 2.0 / (span + 1.0);
    out[0] = x[0];
    for (std::size_t i = 1; i < n; ++i)
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1];
    return out;
}

// ── Returns & volatility ─────────────────────────────────────────────────────

Vec simple_returns(const Vec& price) {
    Vec out;
    if (price.size() < 2) return out;
    out.reserve(price.size() - 1);
    for (std::size_t i = 1; i < price.size(); ++i)
        out.push_back(price[i - 1] != 0.0 ? price[i] / price[i - 1] - 1.0 : 0.0);
    return out;
}

Vec log_returns(const Vec& price) {
    Vec out;
    if (price.size() < 2) return out;
    out.reserve(price.size() - 1);
    for (std::size_t i = 1; i < price.size(); ++i)
        out.push_back((price[i] > 0.0 && price[i-1] > 0.0)
                      ? std::log(price[i] / price[i - 1]) : 0.0);
    return out;
}

double realized_vol(const Vec& returns, double ppy) {
    std::size_t n = returns.size();
    if (n < 2) return NaN;
    double mean = std::accumulate(returns.begin(), returns.end(), 0.0) / n;
    double ss = 0.0;
    for (double r : returns) ss += (r - mean) * (r - mean);
    double var = ss / (n - 1);
    return std::sqrt(var) * std::sqrt(ppy);
}

Vec rolling_realized_vol(const Vec& returns, std::size_t window, double ppy) {
    Vec s = rolling_std(returns, window);
    for (double& v : s) if (!std::isnan(v)) v *= std::sqrt(ppy);
    return s;
}

// ── Mean reversion ───────────────────────────────────────────────────────────

double ou_half_life(const Vec& x) {
    std::size_t n = x.size();
    if (n < 3) return NaN;

    // Regress Δx[t] on x[t-1]:  Δx = a + b*x_lag ; half-life = -ln(2)/ln(1+b)
    Vec dx, lag;
    dx.reserve(n - 1); lag.reserve(n - 1);
    for (std::size_t i = 1; i < n; ++i) {
        dx.push_back(x[i] - x[i - 1]);
        lag.push_back(x[i - 1]);
    }
    std::size_t m = dx.size();
    double mx = std::accumulate(lag.begin(), lag.end(), 0.0) / m;
    double my = std::accumulate(dx.begin(),  dx.end(),  0.0) / m;
    double cov = 0.0, varx = 0.0;
    for (std::size_t i = 0; i < m; ++i) {
        cov  += (lag[i] - mx) * (dx[i] - my);
        varx += (lag[i] - mx) * (lag[i] - mx);
    }
    if (varx == 0.0) return NaN;
    double b = cov / varx;
    if (b >= 0.0) return -1.0;  // not mean-reverting
    double hl = -std::log(2.0) / std::log(1.0 + b);
    return hl;
}

double hurst_exponent(const Vec& x) {
    std::size_t raw_n = x.size();
    if (raw_n < 21) return NaN;

    // R/S analysis operates on increments (first differences), not levels.
    Vec d;
    d.reserve(raw_n - 1);
    for (std::size_t i = 1; i < raw_n; ++i) d.push_back(x[i] - x[i - 1]);
    std::size_t n = d.size();
    if (n < 20) return NaN;

    // R/S analysis over several lags, fit log(R/S) ~ H*log(lag)
    std::vector<std::size_t> lags;
    for (std::size_t lag = 8; lag < n / 2; lag *= 2) lags.push_back(lag);
    if (lags.size() < 2) return NaN;

    Vec log_lag, log_rs;
    for (std::size_t lag : lags) {
        std::size_t n_chunks = n / lag;
        double rs_sum = 0.0;
        int valid = 0;
        for (std::size_t c = 0; c < n_chunks; ++c) {
            double mean = 0.0;
            for (std::size_t i = 0; i < lag; ++i) mean += d[c * lag + i];
            mean /= lag;
            double cum = 0.0, mn = 1e18, mx = -1e18, sd = 0.0;
            for (std::size_t i = 0; i < lag; ++i) {
                double dev = d[c * lag + i] - mean;
                cum += dev;
                mn = std::min(mn, cum);
                mx = std::max(mx, cum);
                sd += dev * dev;
            }
            sd = std::sqrt(sd / lag);
            if (sd > 0.0) { rs_sum += (mx - mn) / sd; ++valid; }
        }
        if (valid > 0) {
            log_lag.push_back(std::log((double)lag));
            log_rs.push_back(std::log(rs_sum / valid));
        }
    }
    if (log_lag.size() < 2) return NaN;

    // Linear regression slope = Hurst exponent
    std::size_t m = log_lag.size();
    double mx = std::accumulate(log_lag.begin(), log_lag.end(), 0.0) / m;
    double my = std::accumulate(log_rs.begin(),  log_rs.end(),  0.0) / m;
    double cov = 0.0, varx = 0.0;
    for (std::size_t i = 0; i < m; ++i) {
        cov  += (log_lag[i] - mx) * (log_rs[i] - my);
        varx += (log_lag[i] - mx) * (log_lag[i] - mx);
    }
    return varx > 0.0 ? cov / varx : NaN;
}

// ── Cross-sectional ──────────────────────────────────────────────────────────

Vec zscore(const Vec& x) {
    std::size_t n = x.size();
    Vec out(n, NaN);
    if (n < 2) return out;
    double mean = std::accumulate(x.begin(), x.end(), 0.0) / n;
    double ss = 0.0;
    for (double v : x) ss += (v - mean) * (v - mean);
    double sd = std::sqrt(ss / (n - 1));
    if (sd == 0.0) return Vec(n, 0.0);
    for (std::size_t i = 0; i < n; ++i) out[i] = (x[i] - mean) / sd;
    return out;
}

Vec rank_normalize(const Vec& x) {
    std::size_t n = x.size();
    Vec out(n, NaN);
    if (n == 0) return out;
    std::vector<std::size_t> idx(n);
    std::iota(idx.begin(), idx.end(), 0);
    std::sort(idx.begin(), idx.end(), [&](std::size_t a, std::size_t b){ return x[a] < x[b]; });
    for (std::size_t r = 0; r < n; ++r)
        out[idx[r]] = (n > 1) ? (double)r / (double)(n - 1) : 0.5;
    return out;
}

double correlation(const Vec& a, const Vec& b) {
    std::size_t n = std::min(a.size(), b.size());
    if (n < 2) return NaN;
    double ma = std::accumulate(a.begin(), a.begin()+n, 0.0) / n;
    double mb = std::accumulate(b.begin(), b.begin()+n, 0.0) / n;
    double cov = 0.0, va = 0.0, vb = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        cov += (a[i]-ma)*(b[i]-mb);
        va  += (a[i]-ma)*(a[i]-ma);
        vb  += (b[i]-mb)*(b[i]-mb);
    }
    return (va > 0 && vb > 0) ? cov / std::sqrt(va*vb) : NaN;
}

double beta(const Vec& asset, const Vec& bench) {
    std::size_t n = std::min(asset.size(), bench.size());
    if (n < 2) return NaN;
    double ma = std::accumulate(asset.begin(), asset.begin()+n, 0.0)/n;
    double mb = std::accumulate(bench.begin(), bench.begin()+n, 0.0)/n;
    double cov=0.0, varb=0.0;
    for (std::size_t i=0;i<n;++i){ cov+=(asset[i]-ma)*(bench[i]-mb); varb+=(bench[i]-mb)*(bench[i]-mb);}
    return varb>0.0 ? cov/varb : NaN;
}

// ── Performance stats ────────────────────────────────────────────────────────

PerfStats perf_stats(const Vec& r, double rf, double ppy) {
    PerfStats p{};
    std::size_t n = r.size();
    if (n == 0) return p;

    // Cumulative / total return
    double cum = 1.0;
    for (double x : r) cum *= (1.0 + x);
    p.total_return = cum - 1.0;
    p.ann_return   = std::pow(cum, ppy / n) - 1.0;

    // Vol & Sharpe
    double mean = std::accumulate(r.begin(), r.end(), 0.0) / n;
    double ss = 0.0; for (double x : r) ss += (x-mean)*(x-mean);
    double sd = n>1 ? std::sqrt(ss/(n-1)) : 0.0;
    p.ann_vol = sd * std::sqrt(ppy);
    double rf_per = rf / ppy;
    p.sharpe = sd>0.0 ? (mean - rf_per)/sd * std::sqrt(ppy) : 0.0;

    // Sortino (downside deviation)
    double dss = 0.0; int dn = 0;
    for (double x : r) if (x < rf_per) { dss += (x-rf_per)*(x-rf_per); ++dn; }
    double dd = dn>0 ? std::sqrt(dss/dn) : 0.0;
    p.sortino = dd>0.0 ? (mean - rf_per)/dd * std::sqrt(ppy) : 0.0;

    // Max drawdown
    double peak = 1.0, eq = 1.0, maxdd = 0.0;
    for (double x : r) {
        eq *= (1.0 + x);
        peak = std::max(peak, eq);
        maxdd = std::min(maxdd, eq/peak - 1.0);
    }
    p.max_drawdown = maxdd;
    p.calmar = maxdd < 0.0 ? p.ann_return / (-maxdd) : 0.0;

    // Trade stats
    int wins=0, losses=0; double sw=0.0, sl=0.0;
    for (double x : r) {
        if (x > 0) { ++wins; sw += x; }
        else if (x < 0) { ++losses; sl += x; }
    }
    p.n_trades   = (int)n;
    p.hit_rate   = n>0 ? (double)wins/n : 0.0;
    p.avg_win    = wins>0 ? sw/wins : 0.0;
    p.avg_loss   = losses>0 ? sl/losses : 0.0;
    p.profit_factor = sl != 0.0 ? sw / (-sl) : 0.0;

    return p;
}

} // namespace quant
