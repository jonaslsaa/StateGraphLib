from collections import defaultdict
from typing import List, Dict, Literal, TypeVar, Union, Set
from abc import ABC, abstractmethod
from pydantic import BaseModel
from collections import deque

from StateNode import StateNode
from common import CycleDetectedError

class StateGraph:
    def __init__(self):
        self.roots: Set[StateNode] = set()
        self.nodes: Set[StateNode] = set()
    
    def mark_as_roots(self, nodes: Union[StateNode, List[StateNode]]):
        '''
        Mark the nodes as roots of the graph. This will also add the nodes to the graph.
        '''
        if isinstance(nodes, StateNode):
            nodes = [nodes]
        for node in nodes:
            # Check if this creates a cycle
            for other_node in self.nodes:
                if other_node is node:
                    continue
                has_cycle = self._check_cycle(node, other_node, set())
                if has_cycle:
                    raise CycleDetectedError("You cannot create a cycle with a root node")
            self.roots.add(node)
            self.nodes.add(node)
        return self
    
    def connect(self, parent: StateNode, child: StateNode, allow_cycle: bool = False):
        '''
        Connect the parent node to the child node directed edge). This will also add the nodes to the graph.
        parent: The parent node
        child: The child node
        allow_cycle: If True, the connection will be made even if it creates a cycle. Default is False. Never if the parent is a root node.
        '''
        assert parent is not child, "Parent and child cannot be the same"
        
        # Check if this addition will create a cycle
        has_cycle = self._check_cycle(parent, child, set())
        if has_cycle and not allow_cycle:
            raise CycleDetectedError("You can allow cycles by setting allow_cycle=True")
        if has_cycle and parent in self.roots:
            raise CycleDetectedError("You cannot create a cycle with a root node")
        
        # Connect the nodes
        parent.children.add(child)
        child.parents.add(parent)
        # Add the nodes to the set
        self.nodes.add(parent)
        self.nodes.add(child)
        return self
    
    def _check_cycle(self, parent: StateNode, child: StateNode, visited: Set[StateNode]):
        if parent == child:
            return True
        visited.add(parent)
        for node in parent.children:
            if node in visited:
                continue
            if self._check_cycle(node, child, visited):
                return True
        return False
    
    def _build_graph(self):
        node_to_layer_number = {}
        # Count the layers and assign them to the nodes
        for root in self.roots:
            self._count_layers(root, 0, node_to_layer_number)
            
        # Raise if not all nodes have a layer number
        for node in self.nodes:
            if node not in node_to_layer_number:
                raise ValueError(f"Node {node} does not have a layer number")
            
        return node_to_layer_number
    
    def _count_layers(self, node: StateNode, layer_number: int, node_to_layer_number: Dict[StateNode, int]):
        if node in node_to_layer_number:
            return
        node_to_layer_number[node] = layer_number
        for child in node.children:
            self._count_layers(child, layer_number + 1, node_to_layer_number)
    
    def notify_roots(self):
        '''
        Notifies all the root nodes that they should be processed.
        '''
        for root in self.roots:
            root._notified = True
        return self
    
    def process(self, maximum_cycle_calls: int = 2):
        '''
        Process the graph. This will process the nodes in the order of their layers.
        maximum_cycle_calls: The maximum number of times a node can be called in a cycle. Default is 2. Raises an error if the limit is exceeded.
        '''
        node_to_layer_number = self._build_graph()
        node_to_call_count = defaultdict(int)
        # Process the nodes in layers
        for node in sorted(self.nodes, key=lambda x: node_to_layer_number[x]):
            # print(f"On Layer {node_to_layer_number[node]}")
            node.process_wrapper()
            node_to_call_count[node] += 1
            if node_to_call_count[node] > maximum_cycle_calls:
                raise ValueError(f"Maximum cycle calls exceeded for node {node}")
        return self