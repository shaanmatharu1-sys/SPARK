"""
analytics/network/engine.py
Correlation-network builder. Takes price series for a set of symbols, computes
the return-correlation matrix, and emits a graph: nodes (stocks) + edges
(correlations above a threshold), with simple cluster detection.

This is the "map of correlated stocks" — statistical relationships, the quant
analogue of a supply-chain/relationship map.
"""
import sys
import os
import math
import logging

logger = logging.getLogger(__name__)

_quant_path = os.path.join(os.path.dirname(__file__), "..", "..", "cpp_ext", "quant")
sys.path.insert(0, os.path.abspath(_quant_path))

try:
    import quant_module as q
    HAS_QUANT = True
except ImportError:
    HAS_QUANT = False


def _returns(prices):
    return q.simple_returns([float(p) for p in prices if p is not None])


def build_network(universe: dict[str, list[float]],
                  threshold: float = 0.4,
                  sectors: dict[str, str] = None) -> dict:
    """
    universe:  {symbol: [aligned close prices]}
    threshold: min |correlation| to draw an edge
    sectors:   optional {symbol: sector} for coloring/grouping
    Returns {nodes, edges, clusters}.
    """
    if not HAS_QUANT:
        return {"error": "quant_module not compiled"}

    symbols = [s for s, p in universe.items() if len(p) >= 30]
    if len(symbols) < 2:
        return {"error": "need >= 2 symbols with 30+ points", "symbols": symbols}

    min_len = min(len(universe[s]) for s in symbols)
    rets = {s: _returns(universe[s][-min_len:]) for s in symbols}

    # Pairwise correlations -> edges
    edges = []
    adj = {s: [] for s in symbols}
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            a, b = symbols[i], symbols[j]
            c = q.correlation(rets[a], rets[b])
            if c != c:  # NaN
                continue
            if abs(c) >= threshold:
                edges.append({"source": a, "target": b, "weight": round(c, 3)})
                adj[a].append(b)
                adj[b].append(a)

    # Node degree = how connected each name is
    nodes = []
    for s in symbols:
        # average abs correlation to everything else = "centrality" proxy
        cors = [abs(q.correlation(rets[s], rets[o])) for o in symbols if o != s]
        cors = [c for c in cors if c == c]
        avg_corr = sum(cors) / len(cors) if cors else 0
        nodes.append({
            "id":        s,
            "degree":    len(adj[s]),
            "avg_corr":  round(avg_corr, 3),
            "sector":    (sectors or {}).get(s, "Unknown"),
        })

    # Simple cluster detection: connected components on the edge graph
    clusters = _connected_components(symbols, adj)

    return {
        "nodes":     nodes,
        "edges":     edges,
        "clusters":  clusters,
        "n_nodes":   len(nodes),
        "n_edges":   len(edges),
        "threshold": threshold,
    }


def _connected_components(symbols, adj):
    """Group symbols into clusters by graph connectivity."""
    seen = set()
    clusters = []
    for s in symbols:
        if s in seen:
            continue
        # BFS
        comp = []
        stack = [s]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.append(n)
            stack.extend(x for x in adj[n] if x not in seen)
        clusters.append(sorted(comp))
    # Sort largest first
    clusters.sort(key=len, reverse=True)
    return clusters
