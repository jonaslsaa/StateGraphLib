from json import JSONDecodeError
from typing import Dict, Set, Tuple, Type
from pydantic import BaseModel
from pydantic_core import ValidationError

from . import StateGraph, StateNode

StrOrInt = str | int

class SerializedNode(BaseModel):
    id: StrOrInt
    class_name: str
    version: StrOrInt
    serialized_state: str
    
    def __hash__(self) -> int:
        return hash(self.id) + hash(self.class_name) + hash(self.version) + hash(self.serialized_state)

class SerializedGraph(BaseModel):
    nodes: Set[SerializedNode]
    connections: Set[Tuple[StrOrInt, StrOrInt]]

class DeserializationError(Exception):
    pass

class VersionMismatchError(DeserializationError):
    pass

class UnknownNodeError(DeserializationError):
    pass


class GraphSerializer:
    
    @staticmethod
    def serialize(graph: StateGraph) -> SerializedGraph:
        nodes = set()
        connections = set()
        id_counter = 0
        node_to_id = {}
        # Serialize the nodes
        for node in graph.nodes:
            id_counter += 1
            node_id = id_counter
            node_to_id[node] = node_id
            nodes.add(SerializedNode(id=node_id,
                                        class_name=type(node).__name__,
                                        version=node.VERSION,
                                        serialized_state=node.state().model_dump_json())
                    )
        
        # Serialize the connections
        for node in graph.nodes:
            for child in node._children:
                connections.add((node_to_id[node], node_to_id[child]))
        return SerializedGraph(nodes=nodes, connections=connections)
    
    @staticmethod
    def _id_to_nodes(nodes: Set[SerializedNode], node_classes: Dict[str, Type[StateNode]], reinitialize_on_error: bool) -> Dict[StrOrInt, StateNode]:
        id_to_node = {}
        for serialized_node in nodes:
            # Try to find the class for the node
            try:
                node_class = node_classes[serialized_node.class_name]
            except KeyError:
                raise UnknownNodeError(f"Unknown node class {serialized_node.class_name}")
            
            # Check if the version matches
            if node_class.VERSION != serialized_node.version:
                raise VersionMismatchError(f"Version mismatch for node {serialized_node.id}. Expected {node_class.VERSION}, got {serialized_node.version}")
            
            # Deserialize the node
            try:
                node = node_class.from_serialized(serialized_node.serialized_state)
            except (ValidationError, TypeError, JSONDecodeError) as e:
                # If the node cannot be deserialized, we can either skip it or reinitialize it
                if not reinitialize_on_error:
                    raise DeserializationError(f"Error deserializing node {serialized_node.id}: {e}")
                node = node_class.from_defaults()
                
            # Add the node to the dictionary
            id_to_node[serialized_node.id] = node
        return id_to_node
    
    @staticmethod
    def deserialize(serialized_graph: SerializedGraph,
                    node_classes: Set[Type[StateNode]],
                    reinitialize_on_error: bool = False) -> StateGraph:
        graph = StateGraph()
        
        node_classes_dict = {node_class.__name__: node_class for node_class in node_classes}
        print('node_classes_dict', node_classes_dict)
        
        id_to_node = GraphSerializer._id_to_nodes(serialized_graph.nodes, node_classes_dict, reinitialize_on_error=reinitialize_on_error)
    
        for parent_id, child_id in serialized_graph.connections:
            assert parent_id in id_to_node, f"Parent node {parent_id} not found"
            assert child_id in id_to_node, f"Child node {child_id} not found"
            
            parent = id_to_node[parent_id]
            child = id_to_node[child_id]
            graph.connect(parent, child)
            
        return graph