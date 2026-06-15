#pragma once
#include <cmath>
#include <vector>
#include <stdexcept>

namespace greeks {

// ── Normal distribution helpers ──────────────────────────────────────────────

inline double norm_pdf(double x) {
    return (1.0 / std::sqrt(2.0 * M_PI)) * std::exp(-0.5 * x * x);
}

inline double norm_cdf(double x) {
    return 0.5 * std::erfc(-x * M_SQRT1_2);
}

// ── Greeks result struct ─────────────────────────────────────────────────────

struct Greeks {
    double price;
    double delta;
    double gamma;
    double vega;
    double theta;
    double rho;
    double iv;       // implied volatility (populated separately)
};

// ── Black-Scholes core ───────────────────────────────────────────────────────

/**
 * Compute option price and all Greeks.
 * @param S     underlying price
 * @param K     strike price
 * @param T     time to expiration in years
 * @param r     risk-free rate (decimal, e.g. 0.05)
 * @param sigma volatility (decimal, e.g. 0.25)
 * @param is_call true for call, false for put
 */
Greeks compute_greeks(double S, double K, double T, double r, double sigma, bool is_call);

/**
 * Compute implied volatility via Newton-Raphson iteration.
 * @param market_price  observed option mid-price
 * @param S, K, T, r    as above
 * @param is_call       option type
 * @param max_iter      max Newton-Raphson iterations
 * @param tol           convergence tolerance
 * @returns IV as decimal, or -1.0 if no convergence
 */
double implied_volatility(double market_price, double S, double K, double T, double r,
                          bool is_call, int max_iter = 100, double tol = 1e-6);

/**
 * Compute IV surface: matrix of IVs for a grid of strikes and expirations.
 * @param market_prices  2D vector [n_expirations][n_strikes]
 * @param S              underlying price
 * @param strikes        vector of strikes
 * @param expirations    vector of T values (years)
 * @param r              risk-free rate
 * @param is_call        option type
 */
std::vector<std::vector<double>> iv_surface(
    const std::vector<std::vector<double>>& market_prices,
    double S,
    const std::vector<double>& strikes,
    const std::vector<double>& expirations,
    double r,
    bool is_call
);

} // namespace greeks
