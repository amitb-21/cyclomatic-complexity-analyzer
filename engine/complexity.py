from collections.abc import Sized

def calculate_complexity(cfg, components=1):
    """
    Calculate cyclomatic complexity from a control-flow graph.

    V(G) = E - N + 2P

    E = number of edges
    N = number of nodes
    P = number of connected components (for one function, P = 1)
    """
    nodes = len(cfg.nodes)
    graph_edges = getattr(cfg, "edges", None)
    if graph_edges is None:
        get_edges = getattr(cfg, "get_edges", None)
        if not callable(get_edges):
            raise TypeError("CFG must provide edges or a get_edges() method")
        graph_edges = get_edges()
    if not isinstance(graph_edges, Sized):
        raise TypeError("CFG edges must be a sized collection")
    edges = len(graph_edges)

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
    from engine.graph_model import ControlFlowGraph

    cfg = ControlFlowGraph()
    for node_id, label in (
        (1, "Entry"),
        (2, "Condition"),
        (3, "True branch"),
        (4, "False branch"),
        (5, "Exit"),
    ):
        cfg.add_node(node_id, label)
    for source, target in ((1, 2), (2, 3), (2, 4), (3, 5), (4, 5)):
        cfg.add_edge(source, target)

    result = calculate_complexity(cfg)

    print("Nodes:", result["nodes"])
    print("Edges:", result["edges"])
    print("Components:", result["components"])
    print("Cyclomatic Complexity:", result["complexity"])
