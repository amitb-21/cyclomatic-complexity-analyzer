from graphviz import Digraph


def render_cfg(cfg, output_path="cfg_graph"):
    """Render a standardized CFG to a PNG image."""
    graph = Digraph("CFG", format="png")

    graph.attr(
        rankdir="TB",
        label="Control Flow Graph",
        labelloc="t",
    )
    graph.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor="lightblue",
        fontname="Arial",
    )
    graph.attr("edge", fontname="Arial", fontsize="10")

    # cfg.nodes is a dictionary: {node_id: CFGNode}.
    for node_id, node in cfg.nodes.items():
        identifier = str(node.node_id)
        label = str(node.label)

        if label == "Entry":
            graph.node(
                identifier,
                label,
                shape="oval",
                fillcolor="lightgreen",
            )
        elif label == "Exit":
            graph.node(
                identifier,
                label,
                shape="oval",
                fillcolor="lightcoral",
            )
        else:
            graph.node(identifier, label)

    # The standardized CFG exposes edges through get_edges().
    for source_id, target_id in cfg.get_edges():
        edge_label = cfg.edge_labels.get(
            (source_id, target_id), ""
        )

        graph.edge(
            str(source_id),
            str(target_id),
            label=edge_label,
        )

    output_file = graph.render(output_path, cleanup=True)
    print(f"CFG image saved to: {output_file}")

    return output_file
