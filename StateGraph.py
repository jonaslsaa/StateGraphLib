from collections import defaultdict
from typing import List, Dict, Literal, TypeVar, Union, Set
from abc import ABC, abstractmethod
from pydantic import BaseModel
from collections import deque

from StateNode import StateNode
from common import CycleDetectedError


def highest_notified_ancestors(node: StateNode):
    """
    Returns a list of the highest notified ancestors of the given node.

    Args:
        node (StateNode): The node for which to find the highest notified ancestors.

    Returns:
        list: A list of StateNode objects representing the highest notified ancestors, these are the nodes that have been notified and are the highest in their hierarchy.
    """
    notified_dependents = []
    # For each parent, get the highest notified ancestor
    for p in node._parents:
        others = highest_notified_ancestors(p)
        notified_dependents.extend(others)
    # If any parent is notified, return the parent as it is the highest notified ancestor
    if len(notified_dependents) > 0:
        return notified_dependents
    # If no parent is notified, return the node if it is notified
    if node._notified:
        return [node]
    # If the node is not notified, return empty
    return []

def nodeset_get_notified(nodes: Set[StateNode]):
    '''
    Returns a set of nodes that have been notified.
    '''
    return {node for node in nodes if node._notified}

def nodeset_get_children(nodes: Set[StateNode]):
    '''
    Returns a set of children of the nodes.
    '''
    children = set()
    for node in nodes:
        children.update(node._children)
    return children

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
        self.nodes.add(parent)
        self.nodes.add(child)
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

    def _find_roots(self):
        roots = set()
        for node in self.nodes:
            if len(node._parents) == 0:
                roots.add(node)
        return roots
    
    def notify_all(self):
        '''
        Notifies all nodes. This is useful when initializing a new graph.
        '''
        for root in self._find_roots():
            root._notify()
        return self
    
    def _layer_depth(self, node: StateNode, visited: Set[StateNode], depth: int):
        if node in visited:
            return depth
        visited.add(node)
        max_depth = depth
        for child in node._children:
            max_depth = max(max_depth, self._layer_depth(child, visited, depth + 1))
        return max_depth
        
    def next_batch(self):
        '''
        Returns the next batch of nodes that can be processed, these nodes will not be dependent on each other.
        '''
        all_notified = nodeset_get_notified(self.nodes)
        
        # For each node, find highest notified ancestor
        highest_notified = set()
        for node in all_notified:
            highest_notified.update(highest_notified_ancestors(node))
        
        return highest_notified