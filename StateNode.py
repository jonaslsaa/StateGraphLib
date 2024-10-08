from collections import defaultdict
from enum import Enum
from typing import Any, Callable, List, Dict, Literal, TypeVar, Union, Set, TYPE_CHECKING
from abc import ABC, abstractmethod
from pydantic import BaseModel
from .encoders import jsonable_encoder
from collections import deque

if TYPE_CHECKING:
    from .StateNode import StateNode

from .common import NodeNotFoundError

def pydantic_deep_eq(a: BaseModel, b: BaseModel) -> bool:
    # Try to get _PRIVATE attribute
    private_a = getattr(a, "_PRIVATE", [])
    private_b = getattr(b, "_PRIVATE", [])
    return a.model_dump(exclude=private_a) == b.model_dump(exclude=private_b)

class StateNode(ABC):
    
    VERSION = "1.0.0"
    
    class SetStateMode(Enum):
        SILENT = 0
        NOTIFY_CHILDREN = 1
        DEEP_COMPARE = 2
    
    class State(BaseModel):
        ''' Pydantic validation model for the state of the node. This class should be implemented by the child class '''
        pass
    
    def __init__(self):
        '''
            Usually, this shouldn't be overridden by the child class, or directly called upon.
            Use `from_serialized` or `from_dict` instead.
        '''
        self._parents: Set[StateNode] = set()
        self._children: Set[StateNode] = set()
        self._state: StateNode.State = None
        self._prev_state: StateNode.State = None # prev_state is used for children nodes to detect spesific changes.
        self._notified: bool = False
        self.post_init()
    
    def post_init(self):
        '''
        This method can be implemented by the child class. This method is called after the node is initialized.
        '''
        pass
    
    def state(self) -> State:
        return self._state
    
    def set_state(self, state: State, notification_mode: SetStateMode = SetStateMode.DEEP_COMPARE):
        '''
        This method sets the state of the node if the state is valid. It notifies children if the state has changed.
        Throws ValidationError if the state is invalid.
        
        Notification modes:
        - SILENT: The state is set silently without notifying children.
        - NOTIFY_CHILDREN: The state is set and children are always notified. (can be useful when state is very complex)
        - DEEP_COMPARE: The state is set and children are notified only if the state has changed. (Recommended for most cases)
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
        elif notification_mode == self.SetStateMode.DEEP_COMPARE \
                and not pydantic_deep_eq(self._state, model_copy):
            # Notify children if the state has changed
            self._notify_children()
        return self
    
    def prev_state(self) -> State:
        '''
        Previous state from last cycle (last run of graph).
        Use in conjunction with auto_finish_cycle=True for StateGraph.next_batch(), or by manually calling StateGraph.finish_cycle()
        '''
        return self._prev_state
    
    def has_changed(self, state_property: Callable[['State'], Any] | str | List[str]) -> bool:
        '''
        Returns True if property of the state has changed based on the previous state, False otherwise.
        @example
        ```
        if node.has_changed("property"):
            # Property has changed
        ```
        or
        ```
        if node.has_changed(["first", "second"]):
            # node.first.second has changed
        ```
        or
        ```
        if node.has_changed(lambda state: state.property):
            # Property has changed
        ```
        '''
        
        def compare_deep(a, b):
            # Check if the values are equal
            # Check if their types are the same
            if type(a) != type(b):
                return True
            # If the value inherits from BaseModel, use deep comparison
            if isinstance(a, BaseModel):
                return not pydantic_deep_eq(a, b)
            # If the value is a primitive type, use normal comparison
            if isinstance(a, (int, float, str, bool, type(None))):
                return a != b
            # Otherwise try to use json comparison
            return jsonable_encoder(a) != jsonable_encoder(b)
        
        if callable(state_property):
            getter: Callable[[StateNode.State], Any] = state_property
            # Get the current and previous values
            current_value = getter(self.state())
            if self.prev_state() is None:
                raise ValueError("No previous state to compare, node has not been initialized correctly. Use load_from_serialized, load_from_dict or from_defaults instead.")
            prev_value = getter(self.prev_state())
            return compare_deep(current_value, prev_value)
        # If the property is a string or a list of strings
        # Convert the string to a list
        if isinstance(state_property, str):
            state_property = state_property.split(".")
        # Traverse the state to get the value
        if isinstance(state_property, list):
            state = self.state()
            prev_state = self.prev_state()
            for prop in state_property:
                state = getattr(state, prop)
                prev_state = getattr(prev_state, prop)
            return compare_deep(state, prev_state)
        raise ValueError("state_property should be a callable or a string")
    
    def serialize(self):
        '''
        This method serializes the state of the node to a JSON string.
        '''
        self.validate_state()
        return self._state.model_dump_json()

    def validate_state(self):
        '''
        This method validates the state of the node.
        :raises ValidationError if the state is invalid.
        '''
        self._state.model_validate(self._state.model_dump())
        
    def process(self):
        '''
        Call this method to process the node. Notifies children if the state has changed, and validates the state.
        It should not be overridden by the child class.
        '''
        assert self._state is not None, "State is not initialized, this might be due to instantiating the node directly. Use load_from_serialized, load_from_dict or from_defaults instead."
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
        # Validate the state
        self.validate_state()
        # Reset notified flag
        self._notified = False
    
    def notify(self):
        '''
        Mark the node to be processed. Usually called on root nodes.
        If you have externally changed the state of the node, call apply_change() instead.
        '''
        self._notified = True
    
    def _notify_children(self):
        '''
        Notifies all the children of the node indicating that a dependent state has changed. Marks them to be processed.
        '''
        for child in self._children:
            child.notify()
    
    def apply_change(self, force_notify: bool = False):
        '''
        This method should be called when the state of the node has been manually changed. It notifies children and validates the state.
        :raises ValidationError if the state is invalid.
        '''
        self.validate_state()
        # Check if the state has changed
        if not force_notify and pydantic_deep_eq(self._state, self._prev_state):
            return False
        # If so, notify children
        self._notify_children()
        return True
    
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
    def from_serialized(cls, serialized_data: str, node_init_args: Dict[str, any] = {}):
        '''
        Loads the node from a serialized JSON string.
        '''
        node = cls(**node_init_args)
        return node.load_from_serialized(serialized_data)
    
    @classmethod
    def from_dict(cls, data: dict, node_init_args: Dict[str, any] = {}):
        '''
        Loads the node from a dictionary.
        '''
        node = cls(**node_init_args)
        return node.load_from_dict(data)
    
    def load_from_serialized(self, serialized_data: str):
        '''
        Loads the node from a serialized JSON string.
        '''
        self._state = self.State.model_validate_json(serialized_data)
        self._prev_state = self._state.model_copy(deep=True)
        return self

    def load_from_dict(self, data: dict):
        '''
        Loads the node from a dictionary.
        '''
        self._state = self.State.model_validate(data)
        self._prev_state = self._state.model_copy(deep=True)
        return self
    
    @classmethod
    def from_defaults(cls, node_init_args: Dict[str, any] = {}):
        '''
        This method can be implemented by the child class. This method should return a new instance of the class with a valid default state. Use `load_from_dict`
        By default, it returns an instance with empty state - this might fail.
        '''
        # assert that all arguments are provided
        node = cls(**node_init_args)
        return node.load_from_dict({})
        
    
    @abstractmethod
    def on_notify(self):
        '''
        This method should be implemented by the child class. This method is called by self.process() method and shouldn't be called directly.
        If state is changed here, it will notify children.
        '''
        raise NotImplementedError("on_notify() method is not implemented")
