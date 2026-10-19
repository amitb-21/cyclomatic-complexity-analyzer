from collections import defaultdict
from collections.abc import Iterable
from types import SimpleNamespace

from engine.complexity import calculate_complexity
from engine.linear_algebra import binary_rank


def _normalize_cfg(cfg):
    """Return CFG nodes and edges in the format used by this module."""
    raw_nodes = cfg.nodes
    node_items = (
        raw_nodes.items()
        if isinstance(raw_nodes, dict)
        else ((None, node) for node in raw_nodes)
    )

    nodes = {}
    for node_key, node in node_items:
        node_id = getattr(node, "id", getattr(node, "node_id", node_key))
        label = getattr(
            node,
            "label",
            node if isinstance(node, str) else None,
        )
        if node_id is None or label is None:
            raise ValueError("CFG nodes must provide an ID and label")
        nodes[node_id] = SimpleNamespace(id=node_id, label=label)

    edges = getattr(cfg, "edges", None)
    if edges is None:
        get_edges = getattr(cfg, "get_edges", None)
        if not callable(get_edges):
            raise TypeError("CFG must provide edges or a get_edges() method")
        edges = get_edges()
    if not isinstance(edges, Iterable):
        raise TypeError("CFG edges must be an iterable collection")

    normalized_edges = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) < 2:
            raise ValueError("CFG edges must contain source and target IDs")
        try:
            source, target, *metadata = edge
        except ValueError as error:
            raise ValueError("CFG edges must contain source and target IDs") from error
        label = metadata[0] if metadata else ""
        normalized_edges.append((source, target, label))

    return nodes, normalized_edges


def find_all_paths(
    cfg,
    entry_label="Entry",
    exit_label="Exit",
    max_edge_uses=2,
    max_candidates=20000,
):
    """
    Generate bounded directed Entry-to-Exit walks.

    Returns:
        paths: list of (node_path, edge_path) tuples
        nodes: dictionary mapping node IDs to node objects

    This search is bounded and cannot guarantee that every possible
    independent execution path will be discovered.
    """
    if max_edge_uses < 1:
        raise ValueError("max_edge_uses must be at least 1")

    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")

    nodes, edges = _normalize_cfg(cfg)

    entries = [
        node.id for node in nodes.values()
        if node.label == entry_label
    ]
    exits = [
        node.id for node in nodes.values()
        if node.label == exit_label
    ]

    if not entries or not exits:
        raise ValueError("CFG must contain Entry and Exit nodes")

    entry = entries[0]
    exit_node = exits[0]

    adjacency = defaultdict(list)

    for edge_index, (source, target, label) in enumerate(edges):
        adjacency[source].append((edge_index, target, label))

    paths = []
    edge_counts = [0] * len(edges)
    seen_vectors = set()

    max_length = max(1, len(edges) * max_edge_uses)

    def dfs(current, node_path, edge_path):
        if len(paths) >= max_candidates:
            return

        if current == exit_node:
            vector = _edge_parity_vector(
                edge_path,
                len(edges),
            )
            vector_key = tuple(vector)

            if vector_key not in seen_vectors:
                seen_vectors.add(vector_key)
                paths.append(
                    (node_path.copy(), edge_path.copy())
                )

            return

        if len(edge_path) >= max_length:
            return

        for edge_index, target, _label in adjacency[current]:
            if edge_counts[edge_index] >= max_edge_uses:
                continue

            edge_counts[edge_index] += 1
            edge_path.append(edge_index)
            node_path.append(target)

            dfs(target, node_path, edge_path)

            node_path.pop()
            edge_path.pop()
            edge_counts[edge_index] -= 1

            if len(paths) >= max_candidates:
                return

    dfs(entry, [entry], [])

    return paths, nodes


def _edge_parity_vector(edge_path, edge_count):
    """
    Represent a path using edge-traversal parity.

    Each position is 1 if that edge is traversed an odd number
    of times, otherwise 0.
    """
    vector = [0] * edge_count

    for edge_index in edge_path:
        vector[edge_index] ^= 1

    return vector


def _select_independent_path_ids(cfg):
    """
    Greedily select candidate paths independent over GF(2).

    The result is a heuristic candidate basis. The bounded search
    does not guarantee completeness for arbitrary CFGs.
    """
    all_paths, _nodes = find_all_paths(cfg)
    _nodes, edges = _normalize_cfg(cfg)

    selected_paths = []
    selected_vectors = []
    current_rank = 0

    expected_rank = calculate_complexity(cfg)["complexity"]

    for node_path, edge_path in all_paths:
        vector = _edge_parity_vector(
            edge_path,
            len(edges),
        )

        new_rank = binary_rank(selected_vectors + [vector])

        if new_rank > current_rank:
            selected_paths.append(node_path)
            selected_vectors.append(vector)
            current_rank = new_rank

        if current_rank >= expected_rank:
            break

    if current_rank < expected_rank:
        print(
            "\nWarning: Incomplete path basis. "
            f"Expected rank {expected_rank}, found {current_rank}. "
            "The bounded candidate search may have missed paths."
        )

    return selected_paths, current_rank, expected_rank


def find_independent_paths(cfg):
    """Return selected paths as readable node labels."""
    selected_paths, _rank, _expected = _select_independent_path_ids(cfg)

    nodes, _edges = _normalize_cfg(cfg)

    return [
        [nodes[node_id].label for node_id in path]
        for path in selected_paths
    ]


def find_independent_path_ids(cfg):
    """Return selected paths as node IDs."""
    selected_paths, _rank, _expected = _select_independent_path_ids(cfg)
    return selected_paths


def build_fundamental_cycle_basis(
    cfg,
    entry_label="Entry",
    exit_label="Exit",
):
    """
    Build a fundamental cycle basis using a DFS spanning forest.

    Adds a virtual Exit -> Entry edge for cycle-space analysis.
    The original CFG is not modified.

    IMPORTANT:
        These are undirected cycle-space vectors, not necessarily
        valid directed execution paths.
    """
    nodes, cfg_edges = _normalize_cfg(cfg)

    entries = [
        node.id for node in nodes.values()
        if node.label == entry_label
    ]
    exits = [
        node.id for node in nodes.values()
        if node.label == exit_label
    ]

    if not entries or not exits:
        raise ValueError("CFG must contain Entry and Exit nodes")

    entry = entries[0]
    exit_node = exits[0]

    edges = [
        {
            "id": index,
            "source": source,
            "target": target,
            "label": label,
            "virtual": False,
        }
        for index, (source, target, label) in enumerate(cfg_edges)
    ]

    virtual_edge_id = len(edges)

    edges.append(
        {
            "id": virtual_edge_id,
            "source": exit_node,
            "target": entry,
            "label": "Virtual Exit -> Entry",
            "virtual": True,
        }
    )

    adjacency = {node_id: [] for node_id in nodes}

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        edge_id = edge["id"]

        adjacency[source].append((target, edge_id))
        adjacency[target].append((source, edge_id))

    visited = set()
    tree_edge_ids = set()
    chord_edge_ids = set()
    parent = {}

    def dfs(start):
        visited.add(start)
        stack = [(start, iter(adjacency[start]))]

        while stack:
            current, neighbors = stack[-1]

            try:
                target, edge_id = next(neighbors)
            except StopIteration:
                stack.pop()
                continue

            if (
                edge_id in tree_edge_ids
                or edge_id in chord_edge_ids
            ):
                continue

            if target not in visited:
                tree_edge_ids.add(edge_id)
                parent[target] = (current, edge_id)
                visited.add(target)
                stack.append(
                    (target, iter(adjacency[target]))
                )
            else:
                chord_edge_ids.add(edge_id)

    dfs(entry)

    for node_id in nodes:
        if node_id not in visited:
            dfs(node_id)

    tree_adjacency = {node_id: [] for node_id in nodes}

    for edge in edges:
        if edge["id"] in tree_edge_ids:
            source = edge["source"]
            target = edge["target"]
            edge_id = edge["id"]

            tree_adjacency[source].append((target, edge_id))
            tree_adjacency[target].append((source, edge_id))

    def tree_path_edge_ids(start, goal):
        """Find the unique undirected tree path between two nodes."""
        stack = [(start, [])]
        seen = {start}

        while stack:
            current, path = stack.pop()

            if current == goal:
                return path

            for neighbor, edge_id in tree_adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(
                        (neighbor, path + [edge_id])
                    )

        raise ValueError(
            "Could not find a tree path between chord endpoints"
        )

    cycles = []

    for chord_id in sorted(chord_edge_ids):
        chord = edges[chord_id]

        tree_path = tree_path_edge_ids(
            chord["source"],
            chord["target"],
        )

        cycles.append(
            {
                "chord_edge_id": chord_id,
                "edge_ids": tree_path + [chord_id],
                "contains_virtual_edge": (
                    chord["virtual"]
                    or virtual_edge_id in tree_path
                ),
            }
        )

    component_count = 0
    counted = set()

    for node_id in nodes:
        if node_id in counted:
            continue

        component_count += 1
        stack = [node_id]
        counted.add(node_id)

        while stack:
            current = stack.pop()

            for neighbor, _edge_id in adjacency[current]:
                if neighbor not in counted:
                    counted.add(neighbor)
                    stack.append(neighbor)

    expected_dimension = (
        len(edges) - len(nodes) + component_count
    )

    if len(cycles) != expected_dimension:
        raise AssertionError(
            f"Cycle basis size {len(cycles)} does not match "
            f"expected dimension {expected_dimension}"
        )

    return {
        "tree_edge_ids": sorted(tree_edge_ids),
        "chord_edge_ids": sorted(chord_edge_ids),
        "virtual_edge_id": virtual_edge_id,
        "cycles": cycles,
        "expected_dimension": expected_dimension,
        "component_count": component_count,
        "edges": edges,
        "nodes": nodes,
    }


if __name__ == "__main__":
    from frontend.cpp.parser import CppParser

    filename = "examples/nested_loops.cpp"

    cfg = CppParser().build_cfg(filename)

    print(
        "Cyclomatic Complexity:",
        calculate_complexity(cfg)["complexity"],
    )

    paths = find_independent_paths(cfg)

    print("Independent Paths Found:", len(paths))

    for index, path in enumerate(paths, start=1):
        print(f"\nPath {index}:")
        print(" -> ".join(path))
