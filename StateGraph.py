from collections import defaultdict
from typing import List, Dict, Literal, TypeVar, Union, Set
from abc import ABC, abstractmethod
from pydantic import BaseModel
from collections import deque

from .StateNode import StateNode
from .common import CycleDetectedError

def has_higher_notified_ancestor(node: StateNode):
    """
    Checks if the given node has any notified ancestors.

    This function recursively traverses the parent nodes of the given node to determine if any of them, or their ancestors, have been notified.

    Args:
        node (StateNode): The node for which to check for notified ancestors.

    Returns:
        bool: True if there is at least one notified ancestor, False otherwise.
    """
    for p in node._parents:
        if p._notified:
            return True
        if has_higher_notified_ancestor(p):
            return True
    return False

def nodeset_get_notified(nodes: Set[StateNode]):
    '''
    Returns a set of nodes that have been notified.
    '''
    return {node for node in nodes if node._notified}

class StateGraph:
    def __init__(self):
        self.nodes: Set[StateNode] = set()
    
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
        
        # Connect the nodes
        parent._children.add(child)
        child._parents.add(parent)
        # Add the nodes to the set
        self._add_node(parent)
        self._add_node(child)
        return self
    
    def _add_node(self, node: StateNode):
        assert node.state() is not None, "State is not initialized, this might be due to instantiating the node directly. Use load_from_serialized, load_from_dict or from_defaults instead."
        self.nodes.add(node)
        return self
    
    def _check_cycle(self, parent: StateNode, child: StateNode, visited: Set[StateNode]):
        if parent == child:
            return True
        visited.add(parent)
        for node in parent._children:
            if node in visited:
                continue
            if self._check_cycle(node, child, visited):
                return True
        return False

    def notify_all(self):
        '''
        Notifies all nodes. This is useful when initializing a new graph.
        '''
        for root in self.nodes:
            root.notify()
        return self
        
    def next_batch(self):
            '''
            Returns the next batch of nodes that can be processed, these nodes will not be dependent on each other (can be processed in parallel).
            It will find the highest non-dependent notified nodes and return them. This ensures that changes are propagated in the correct order, parent nodes are processed before children.
            
            Returns:
                set: A set of nodes that can be processed in parallel without dependencies.
            '''
            all_notified = nodeset_get_notified(self.nodes)


            # Find the highest notified nodes
            highest_notified = set()
            # For each node, check if it has a higher notified ancestor, if not, add it as it has no dependencies
            for node in all_notified:
                if not has_higher_notified_ancestor(node):
                    highest_notified.add(node)
            
            return highest_notified
