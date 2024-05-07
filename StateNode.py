from collections import defaultdict
from typing import List, Dict, Literal, TypeVar, Union, Set
from abc import ABC, abstractmethod
from pydantic import BaseModel
from collections import deque

from common import NodeNotFoundError

class StateNode(ABC):
    
    class State(BaseModel):
        ''' This class should be implemented by the child class '''
        pass
    
    def __init__(self):
        '''
            data: Union[str, dict]  If str, it should be a serialized JSON string.
                                    If dict, it should be a dictionary (used for initialization of the state)
        '''
        self.parents: Set[StateNode] = set()
        self.children: Set[StateNode] = set()
        self.state: self.State = None
        self._notified: bool = False
    
    def serialize(self):
        self.validate_state()
        return self.state.model_dump_json()

    def validate_state(self):
        self.state.model_validate(self.state.dict())
        
    def process_wrapper(self):
        print(f"  Processing {self.__class__.__name__}")
        if not self._notified:
            print(f"    Skipping as it was not notified")
            return
        # Copy the state to check if it has changed
        state_copy = self.state.model_copy(deep=True)
        # Process, which may change the state
        self.process()
        # Check if the state has changed
        if self.state != state_copy and len(self.children) > 0:
            # Notify children as their parent has changed
            self.notify_children()
            print(f"    Notified children")
        # Reset notified flag
        self._notified = False
        # Validate the state
        self.validate_state()
    
    def notify_children(self):
        for child in self.children:
            child._notified = True
    
    T = TypeVar('T')
    def get_ancestor(self, cls: T) -> T:
        queue = deque()
        queue.extend(self.parents)
        visited = set()
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if isinstance(node, cls):
                return node
            queue.extend(parent for parent in node.parents if parent not in visited)
        raise NodeNotFoundError(f"Ancestor of type {cls} not found")
    
    @classmethod
    def load_from_serialized(cls, serialized_data: str):
        node = cls()
        node.state = node.State.model_validate_json(serialized_data)
        return node
    
    @classmethod
    def load_from_dict(cls, data: dict):
        node = cls()
        node.state = node.State.model_validate(data)
        return node
    
    @abstractmethod
    def process(self):
        '''
        This method is called by self.process_wrapper() method. This method should be implemented by the child class.
        '''
        raise NotImplementedError("process() method is not implemented")