#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "greeks.h"

namespace py = pybind11;
using namespace pybind11::literals;   // enables the "name"_a keyword-arg syntax

PYBIND11_MODULE(greeks_module, m) {
    m.doc() = "Black-Scholes Greeks engine — compiled C++ via pybind11";

    // ── Greeks result struct ──────────────────────────────────────────────────
    py::class_<greeks::Greeks>(m, "Greeks")
        .def_readonly("price", &greeks::Greeks::price)
        .def_readonly("delta", &greeks::Greeks::delta)
        .def_readonly("gamma", &greeks::Greeks::gamma)
        .def_readonly("vega",  &greeks::Greeks::vega)
        .def_readonly("theta", &greeks::Greeks::theta)
        .def_readonly("rho",   &greeks::Greeks::rho)
        .def_readonly("iv",    &greeks::Greeks::iv)
        .def("to_dict", [](const greeks::Greeks& g) {
            return py::dict(
                "price"_a = g.price,
                "delta"_a = g.delta,
                "gamma"_a = g.gamma,
                "vega"_a  = g.vega,
                "theta"_a = g.theta,
                "rho"_a   = g.rho,
                "iv"_a    = g.iv
            );
        });

    // ── compute_greeks ────────────────────────────────────────────────────────
    m.def("compute_greeks",
        &greeks::compute_greeks,
        py::arg("S"),
        py::arg("K"),
        py::arg("T"),
        py::arg("r"),
        py::arg("sigma"),
        py::arg("is_call") = true,
        R"pbdoc(
            Compute Black-Scholes price and all Greeks.

            Parameters
            ----------
            S       : float  — underlying price
            K       : float  — strike price
            T       : float  — time to expiration in years
            r       : float  — risk-free rate (e.g. 0.05)
            sigma   : float  — volatility (e.g. 0.25)
            is_call : bool   — True for call, False for put

            Returns
            -------
            Greeks object with .price, .delta, .gamma, .vega, .theta, .rho, .iv
        )pbdoc"
    );

    // ── implied_volatility ────────────────────────────────────────────────────
    m.def("implied_volatility",
        &greeks::implied_volatility,
        py::arg("market_price"),
        py::arg("S"),
        py::arg("K"),
        py::arg("T"),
        py::arg("r"),
        py::arg("is_call") = true,
        py::arg("max_iter") = 100,
        py::arg("tol") = 1e-6,
        R"pbdoc(
            Compute implied volatility via Newton-Raphson.
            Returns -1.0 if no convergence.
        )pbdoc"
    );

    // ── iv_surface ────────────────────────────────────────────────────────────
    m.def("iv_surface",
        &greeks::iv_surface,
        py::arg("market_prices"),
        py::arg("S"),
        py::arg("strikes"),
        py::arg("expirations"),
        py::arg("r"),
        py::arg("is_call") = true,
        R"pbdoc(
            Compute IV surface for a grid of strikes and expirations.
            market_prices : list[list[float]]  — [n_expirations][n_strikes]
            Returns       : list[list[float]]  — IV surface (same shape)
        )pbdoc"
    );
}
