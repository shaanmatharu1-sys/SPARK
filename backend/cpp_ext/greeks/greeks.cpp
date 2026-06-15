#include "greeks.h"
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>

namespace greeks {

Greeks compute_greeks(double S, double K, double T, double r, double sigma, bool is_call) {
    if (T <= 0.0)  throw std::invalid_argument("T must be > 0");
    if (S <= 0.0)  throw std::invalid_argument("S must be > 0");
    if (K <= 0.0)  throw std::invalid_argument("K must be > 0");
    if (sigma <= 0.0) throw std::invalid_argument("sigma must be > 0");

    Greeks g;
    g.iv = sigma;

    double sqrt_T  = std::sqrt(T);
    double d1      = (std::log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T);
    double d2      = d1 - sigma * sqrt_T;
    double e_rT    = std::exp(-r * T);
    double pdf_d1  = norm_pdf(d1);

    if (is_call) {
        double Nd1  = norm_cdf(d1);
        double Nd2  = norm_cdf(d2);
        double Nd1n = norm_cdf(-d1);
        double Nd2n = norm_cdf(-d2);

        g.price = S * Nd1  - K * e_rT * Nd2;
        g.delta = Nd1;
        g.gamma = pdf_d1  / (S * sigma * sqrt_T);
        g.vega  = S * pdf_d1 * sqrt_T / 100.0;          // per 1% vol move
        g.theta = (-S * pdf_d1 * sigma / (2.0 * sqrt_T)
                   - r * K * e_rT * Nd2) / 365.0;       // per calendar day
        g.rho   = K * T * e_rT * Nd2 / 100.0;           // per 1% rate move
    } else {
        double Nd1n = norm_cdf(-d1);
        double Nd2n = norm_cdf(-d2);

        g.price = K * e_rT * Nd2n - S * Nd1n;
        g.delta = Nd1n - 1.0;                            // negative for puts
        g.gamma = pdf_d1  / (S * sigma * sqrt_T);        // same as call
        g.vega  = S * pdf_d1 * sqrt_T / 100.0;           // same as call
        g.theta = (-S * pdf_d1 * sigma / (2.0 * sqrt_T)
                   + r * K * e_rT * Nd2n) / 365.0;
        g.rho   = -K * T * e_rT * Nd2n / 100.0;
    }

    return g;
}


double implied_volatility(double market_price, double S, double K, double T, double r,
                          bool is_call, int max_iter, double tol) {
    if (market_price <= 0.0 || T <= 0.0) return -1.0;

    // Initial guess: Brenner-Subrahmanyam approximation
    double sigma = std::sqrt(2.0 * M_PI / T) * (market_price / S);
    sigma = std::max(0.01, std::min(sigma, 5.0));

    for (int i = 0; i < max_iter; ++i) {
        Greeks g;
        try {
            g = compute_greeks(S, K, T, r, sigma, is_call);
        } catch (...) {
            return -1.0;
        }

        double price_diff = g.price - market_price;
        if (std::abs(price_diff) < tol) {
            return sigma;
        }

        // vega is per 1% move, need raw vega for Newton step
        double raw_vega = g.vega * 100.0;
        if (std::abs(raw_vega) < 1e-10) return -1.0;

        sigma -= price_diff / raw_vega;
        sigma  = std::max(0.001, std::min(sigma, 10.0));
    }

    return -1.0;  // no convergence
}


std::vector<std::vector<double>> iv_surface(
    const std::vector<std::vector<double>>& market_prices,
    double S,
    const std::vector<double>& strikes,
    const std::vector<double>& expirations,
    double r,
    bool is_call
) {
    size_t n_exp    = expirations.size();
    size_t n_strikes = strikes.size();

    std::vector<std::vector<double>> surface(n_exp, std::vector<double>(n_strikes, -1.0));

    for (size_t i = 0; i < n_exp; ++i) {
        for (size_t j = 0; j < n_strikes; ++j) {
            if (i < market_prices.size() && j < market_prices[i].size()) {
                surface[i][j] = implied_volatility(
                    market_prices[i][j], S, strikes[j], expirations[i], r, is_call
                );
            }
        }
    }

    return surface;
}

} // namespace greeks
