from collections import defaultdict
from enum import Enum
from typing import List, Dict, Literal, TypeVar, Union, Set
from abc import ABC, abstractmethod
from pydantic import BaseModel
from collections import deque

from .common import NodeNotFoundError

def pydantic_deep_eq(a: BaseModel, b: BaseModel) -> bool:
    # First check using the default equality operator provided by Pydantic
    if a != b:
        # Only reliable way to check if the models are **not** equal
        return False
    # Then check by dumping the models to dict and comparing them, this compares nested models
    return a.model_dump() == b.model_dump()

class StateNode(ABC):
    
    class SetStateMode(Enum):
        SILENT = 0
        NOTIFY_CHILDREN = 1
        DEEP_COMPARE = 2
    
    class State(BaseModel):
        ''' Pydantic validation model for the state of the node. This class should be implemented by the child class '''
        pass
    
    def __init__(self):
        '''
            This shouldn't be overridden by the child class, or directly called upon.
            Use `load_from_serialized` or `load_from_dict` instead.
        '''
        self._parents: Set[StateNode] = set()
        self._children: Set[StateNode] = set()
        self._state: self.State = None
        self._prev_state: self.State = None
        self._notified: bool = False
    
    def state(self) -> State:
        return self._state
    
    def set_state(self, state: State, notification_mode: SetStateMode = SetStateMode.DEEP_COMPARE):
        '''
        This method sets the state of the node if the state is valid. It notifies children if the state has changed.
        Throws ValidationError if the state is invalid.
        
        Notification modes:
        - SILENT: The state is set silently without notifying children.
        - NOTIFY_CHILDREN: The state is set and children are notified. (Useful for performance reasons)
        - DEEP_COMPARE: The state is set and children are notified only if the state has changed.
        '''
        # Validate the state
        state.model_validate(state.model_dump())
        
        # Copy the model for deep comparison (if needed)
        model_copy = None
        if notification_mode == self.SetStateMode.DEEP_COMPARE:
            model_copy = self._state.model_copy(deep=True)
            
        # Set the state
        self._state = state
        
        # Notify children based on the mode
        if notification_mode == self.SetStateMode.NOTIFY_CHILDREN:
            # Notify children if the state has changed
            self._notify_children()
        elif notification_mode == self.SetStateMode.DEEP_COMPARE and not pydantic_deep_eq(self._state, model_copy):
            # Notify children if the state has changed
            self._notify_children()
        return self
    
    def prev_state(self) -> State:
        return self._prev_state
    
    def serialize(self):
        '''
        This method serializes the state of the node to a JSON string.
        '''
        self.validate_state()
        return self._state.model_dump_json()

    def validate_state(self):
        '''
        This method validates the state of the node. Throws ValidationError if the state is invalid.
        '''
        self._state.model_validate(self._state.dict())
        
    def process(self):
        '''
        Call this method to process the node. Notifies children if the state has changed, and validates the state.
        It should not be overridden by the child class.
        '''
        if not self._notified:
            return
        # Copy the state to check if it has changed
        state_copy = self._state.model_copy(deep=True)
        # Process, which may change the state
        self.on_notify()
        # Check if the state has changed
        if len(self._children) > 0 and not pydantic_deep_eq(self._state, state_copy):
            # Notify children as their parent has changed
            self._notify_children()
            # Save the previous state
            self._prev_state = state_copy
        # Reset notified flag
        self._notified = False
        # Validate the state
        self.validate_state()
    
    def _notify(self):
        self._notified = True
    
    def _notify_children(self):
        '''
        Notifies all the children of the node indicating that a dependent state has changed. Marks them to be processed.
        '''
        for child in self._children:
            child._notify()
    
    def apply_change(self):
        '''
        This method should be called when the state of the node has been manually changed. It notifies children and validates the state.
        '''
        self._notify_children()
        self.validate_state()
    
    T = TypeVar('T')
    def get_ancestors(self, cls: T, return_only_first: bool = False) -> Union[T, List[T]]:
        '''
        This method returns all the ancestors of the node that are of the type `cls`.
        '''
        ancestors = []
        queue = deque()
        queue.extend(self._parents)
        visited = set()
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if isinstance(node, cls):
                if return_only_first:
                    return node
                ancestors.append(node)
            queue.extend(parent for parent in node._parents if parent not in visited)
        return ancestors
    
    def get_ancestor(self, cls: T) -> T:
        '''
        This method returns the first ancestor of the node that is of the type `cls`.
        '''
        ancestor = self.get_ancestors(cls, return_only_first=True)
        if isinstance(ancestor, cls):
            return ancestor
        raise NodeNotFoundError(f"Ancestor of type {cls} not found")
    
    @classmethod
    def load_from_serialized(cls, serialized_data: str):
        '''
        Loads the node from a serialized JSON string.
        '''
        node = cls()
        node._state = node.State.model_validate_json(serialized_data)
        return node
    
    @classmethod
    def load_from_dict(cls, data: dict):
        '''
        Loads the node from a dictionary.
        '''
        node = cls()
        node._state = node.State.model_validate(data)
        return node
    
    @classmethod
    def from_defaults(cls):
        '''
        This method can be implemented by the child class. This method should return a new instance of the class with a valid default state. Use `load_from_dict`
        By default, it returns an instance with empty state - this might fail.
        '''
        return cls.load_from_dict({})
    
    @abstractmethod
    def on_notify(self):
        '''
        This method should be implemented by the child class. This method is called by self.process() method and shouldn't be called directly.
        If .state() is changed here, it will notify children.
        '''
        raise NotImplementedError("on_notify() method is not implemented")