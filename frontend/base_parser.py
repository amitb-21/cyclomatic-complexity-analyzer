from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any

class CFGNode:
    """A language-agnostic representation of a code block or statement."""
    def __init__(self, node_id: int, label: str):
        self.node_id = node_id
        self.label = label
        self.successors: List['CFGNode'] = []
    
    def add_successor(self, node: 'CFGNode'):
        if node not in self.successors:
            self.successors.append(node)

class CFG:
    """The standardized Control Flow Graph expected by the math engine."""
    def __init__(self):
        self.nodes: Dict[int, CFGNode] = {}
        self.edge_labels: Dict[Tuple[int, int], str] = {}
        self.start_node: Optional[CFGNode] = None 
        self.end_node: Optional[CFGNode] = None
        
    def add_node(self, node: CFGNode):
        self.nodes[node.node_id] = node

    def add_edge(self, source: CFGNode, target: CFGNode, label: str = ""):
        source.add_successor(target)
        if label:
            self.edge_labels[(source.node_id, target.node_id)] = label

    def get_edges(self) -> List[Tuple[int, int]]:
        """Returns a list of all directed edges (source_id, target_id) for matrix calculations."""
        edges = []
        for node in self.nodes.values():
            for succ in node.successors:
                edges.append((node.node_id, succ.node_id))
        return edges

class BaseParser(ABC):
    """Abstract interface enforcing required methods for all language frontends."""
    
    @abstractmethod
    def parse(self, file_path: str) -> Any:
        """
        Reads the source file and converts it into a language-specific 
        Abstract Syntax Tree (AST) or token stream.
        """
        pass

    @abstractmethod
    def build_cfg(self, file_path: str) -> CFG:
        """
        Orchestrates the parsing and transforms the language-specific AST 
        into the standardized CFG object.
        
        Returns:
            CFG: The language-agnostic control flow graph.
        """
        pass