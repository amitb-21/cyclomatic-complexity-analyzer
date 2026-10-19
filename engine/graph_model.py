class ControlFlowGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, label):
        self.nodes[node_id] = label

    def add_edge(self, source, destination, label=""):
        self.edges.append((source, destination, label))
