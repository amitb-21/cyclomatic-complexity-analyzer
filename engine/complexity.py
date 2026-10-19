
def calculate_complexity(cfg, components=1):
    """
    Calculate cyclomatic complexity from a control-flow graph.

    V(G) = E - N + 2P

    E = number of edges
    N = number of nodes
    P = number of connected components (for one function, P = 1)
    """
    nodes = len(cfg.nodes)
    edges = len(cfg.edges)

    if components < 1:
        raise ValueError("Components must be at least 1")

    complexity = edges - nodes + 2 * components

    return {
        "nodes": nodes,
        "edges": edges,
        "components": components,
        "complexity": complexity,
    }


if __name__ == "__main__":
    from frontend.cpp.cfg_builder import CFGBuilder

    code = """
    int main() {
        int x = 10;
        if (x > 0) {
            x++;
        } else {
            x--;
        }
        return 0;
    }
    """

    cfg = CFGBuilder().build(code)
    result = calculate_complexity(cfg)

    print("Nodes:", result["nodes"])
    print("Edges:", result["edges"])
    print("Components:", result["components"])
    print("Cyclomatic Complexity:", result["complexity"])
