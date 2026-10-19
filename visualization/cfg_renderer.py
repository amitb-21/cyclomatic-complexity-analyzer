
from graphviz import Digraph


def render_cfg(cfg, output_path="cfg_graph"):
    graph = Digraph("CFG", format="png")

    graph.attr(rankdir="TB", label="Control Flow Graph", labelloc="t")
    graph.attr("node", shape="box", style="rounded,filled",
               fillcolor="lightblue", fontname="Arial")
    graph.attr("edge", fontname="Arial", fontsize="10")

    for node in cfg.nodes:
        if node.label == "Entry":
            graph.node(str(node.id), node.label,
                       shape="oval", fillcolor="lightgreen")
        elif node.label == "Exit":
            graph.node(str(node.id), node.label,
                       shape="oval", fillcolor="lightcoral")
        else:
            graph.node(str(node.id), node.label)

    for source, target, label in cfg.edges:
        graph.edge(str(source), str(target), label=label)

    output_file = graph.render(output_path, cleanup=True)
    print(f"CFG image saved to: {output_file}")

    return output_file
