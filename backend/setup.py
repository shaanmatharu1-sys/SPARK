"""
setup.py — Build all C++ extensions with pybind11

Builds two modules:
  - cpp_ext.greeks.greeks_module  (Black-Scholes Greeks, IV surface)
  - cpp_ext.quant.quant_module    (rolling stats, signals, backtest)

Usage:
    pip install pybind11
    python setup.py build_ext --inplace
"""
from setuptools import setup, Extension
import pybind11
import sys

# Shared compile args — note: NO -march=native (breaks universal2 dual-arch builds)
_extra = ["-std=c++17", "-O3"] if sys.platform != "win32" else ["/std:c++17", "/O2"]
_pybind_inc = pybind11.get_include()

ext_modules = [
    Extension(
        name="cpp_ext.greeks.greeks_module",
        sources=[
            "cpp_ext/greeks/greeks.cpp",
            "cpp_ext/greeks/bindings.cpp",
        ],
        include_dirs=[_pybind_inc, "cpp_ext/greeks"],
        language="c++",
        extra_compile_args=_extra,
    ),
    Extension(
        name="cpp_ext.quant.quant_module",
        sources=[
            "cpp_ext/quant/quant_stats.cpp",
            "cpp_ext/quant/backtest.cpp",
            "cpp_ext/quant/bindings.cpp",
        ],
        include_dirs=[_pybind_inc, "cpp_ext/quant"],
        language="c++",
        extra_compile_args=_extra,
    ),
]

setup(
    name="bloomberg_terminal_ext",
    version="1.1.0",
    ext_modules=ext_modules,
)
