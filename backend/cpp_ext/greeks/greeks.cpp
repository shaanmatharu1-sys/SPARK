#include "greeks.h"
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>

namespace greeks {

Greeks compute_greeks(double S, double K, double T, double r, double sigma, bool is_call,
                      double q) {
    if (T <= 0.0)  throw std::invalid_argument("T must be > 0");
    if (S <= 0.0)  throw std::invalid_argument("S must be > 0");
    if (K <= 0.0)  throw std::invalid_argument("K must be > 0");
    if (sigma <= 0.0) throw std::invalid_argument("sigma must be > 0");

    Greeks g;
    g.iv = sigma;

    // Merton (1973): Black-Scholes with a continuous dividend yield q.
    // q = 0 collapses every formula below to plain Black-Scholes.
    double sqrt_T  = std::sqrt(T);
    double d1      = (std::log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T);
    double d2      = d1 - sigma * sqrt_T;
    double e_rT    = std::exp(-r * T);
    double e_qT    = std::exp(-q * T);
    double pdf_d1  = norm_pdf(d1);

    if (is_call) {
        double Nd1  = norm_cdf(d1);
        double Nd2  = norm_cdf(d2);

        g.price = S * e_qT * Nd1 - K * e_rT * Nd2;
        g.delta = e_qT * Nd1;
        g.gamma = e_qT * pdf_d1 / (S * sigma * sqrt_T);
        g.vega  = S * e_qT * pdf_d1 * sqrt_T / 100.0;    // per 1% vol move
        g.theta = (-S * e_qT * pdf_d1 * sigma / (2.0 * sqrt_T)
                   - r * K * e_rT * Nd2
                   + q * S * e_qT * Nd1) / 365.0;         // per calendar day
        g.rho   = K * T * e_rT * Nd2 / 100.0;             // per 1% rate move
    } else {
        double Nd1n = norm_cdf(-d1);
        double Nd2n = norm_cdf(-d2);

        g.price = K * e_rT * Nd2n - S * e_qT * Nd1n;
        g.delta = -e_qT * Nd1n;                           // negative for puts
        g.gamma = e_qT * pdf_d1 / (S * sigma * sqrt_T);   // same as call
        g.vega  = S * e_qT * pdf_d1 * sqrt_T / 100.0;     // same as call
        g.theta = (-S * e_qT * pdf_d1 * sigma / (2.0 * sqrt_T)
                   + r * K * e_rT * Nd2n
                   - q * S * e_qT * Nd1n) / 365.0;
        g.rho   = -K * T * e_rT * Nd2n / 100.0;
    }

    return g;
}


namespace {

// Bisection fallback: Black-Scholes/Merton price is monotonically increasing
// in sigma, so this always converges given a valid bracket, unlike Newton-
// Raphson which can diverge from a bad initial guess (the Brenner-
// Subrahmanyam approximation below is only accurate near-the-money — for
// deep ITM/OTM strikes, especially short-dated ones, it can be off by an
// order of magnitude and send Newton's step outside the feasible region).
double bisect_iv(double market_price, double S, double K, double T, double r,
                 bool is_call, double q, double tol, int max_iter) {
    double lo = 1e-4, hi = 6.0;
    double f_lo, f_hi;
    try {
        f_lo = compute_greeks(S, K, T, r, lo, is_call, q).price - market_price;
        f_hi = compute_greeks(S, K, T, r, hi, is_call, q).price - market_price;
    } catch (...) {
        return -1.0;
    }
    if (f_lo * f_hi > 0.0) return -1.0;  // market price outside the feasible range

    for (int i = 0; i < max_iter; ++i) {
        double mid = 0.5 * (lo + hi);
        double f_mid;
        try {
            f_mid = compute_greeks(S, K, T, r, mid, is_call, q).price - market_price;
        } catch (...) {
            return -1.0;
        }
        if (std::abs(f_mid) < tol) return mid;
        if (f_lo * f_mid < 0.0) { hi = mid; f_hi = f_mid; }
        else                    { lo = mid; f_lo = f_mid; }
    }
    return 0.5 * (lo + hi);
}

} // namespace

double implied_volatility(double market_price, double S, double K, double T, double r,
                          bool is_call, int max_iter, double tol, double q) {
    if (market_price <= 0.0 || T <= 0.0) return -1.0;

    // Initial guess: Brenner-Subrahmanyam approximation
    double sigma = std::sqrt(2.0 * M_PI / T) * (market_price / S);
    sigma = std::max(0.01, std::min(sigma, 5.0));

    for (int i = 0; i < max_iter; ++i) {
        Greeks g;
        try {
            g = compute_greeks(S, K, T, r, sigma, is_call, q);
        } catch (...) {
            break;  // fall through to the bisection fallback below
        }

        double price_diff = g.price - market_price;
        if (std::abs(price_diff) < tol) {
            return sigma;
        }

        // vega is per 1% move, need raw vega for Newton step
        double raw_vega = g.vega * 100.0;
        if (std::abs(raw_vega) < 1e-10) break;  // near-zero vega -> bisection instead

        sigma -= price_diff / raw_vega;
        if (sigma <= 0.0 || sigma > 10.0) break;  // stepped out of range -> bisection instead
    }

    // Newton-Raphson didn't converge (bad initial guess, zero vega, or it
    // stepped outside the valid range) — bisection always converges given
    // a valid bracket, just slower.
    return bisect_iv(market_price, S, K, T, r, is_call, q, tol, 100);
}


std::vector<std::vector<double>> iv_surface(
    const std::vector<std::vector<double>>& market_prices,
    double S,
    const std::vector<double>& strikes,
    const std::vector<double>& expirations,
    double r,
    bool is_call,
    double q
) {
    size_t n_exp    = expirations.size();
    size_t n_strikes = strikes.size();

    std::vector<std::vector<double>> surface(n_exp, std::vector<double>(n_strikes, -1.0));

    for (size_t i = 0; i < n_exp; ++i) {
        for (size_t j = 0; j < n_strikes; ++j) {
            if (i < market_prices.size() && j < market_prices[i].size()) {
                surface[i][j] = implied_volatility(
                    market_prices[i][j], S, strikes[j], expirations[i], r, is_call,
                    100, 1e-6, q
                );
            }
        }
    }

    return surface;
}


double crr_american_price(double S, double K, double T, double r, double sigma,
                          bool is_call, double q, int n_steps) {
    if (T <= 0.0 || S <= 0.0 || K <= 0.0 || sigma <= 0.0) return 0.0;
    if (n_steps < 1) n_steps = 1;

    double dt = T / n_steps;
    double u  = std::exp(sigma * std::sqrt(dt));
    double d  = 1.0 / u;
    double disc = std::exp(-r * dt);
    double p  = (std::exp((r - q) * dt) - d) / (u - d);
    // Guard against a degenerate tree (extreme sigma/dt) producing p outside [0,1]
    p = std::max(0.0, std::min(1.0, p));

    // Terminal payoffs across the n_steps+1 final nodes
    std::vector<double> values(n_steps + 1);
    for (int j = 0; j <= n_steps; ++j) {
        double S_T = S * std::pow(u, j) * std::pow(d, n_steps - j);
        values[j] = is_call ? std::max(S_T - K, 0.0) : std::max(K - S_T, 0.0);
    }

    // Backward induction; at each node take max(continuation, early exercise)
    for (int step = n_steps - 1; step >= 0; --step) {
        for (int j = 0; j <= step; ++j) {
            double continuation = disc * (p * values[j + 1] + (1.0 - p) * values[j]);
            double S_node = S * std::pow(u, j) * std::pow(d, step - j);
            double exercise = is_call ? std::max(S_node - K, 0.0) : std::max(K - S_node, 0.0);
            values[j] = std::max(continuation, exercise);
        }
    }

    return values[0];
}

} // namespace greeks
