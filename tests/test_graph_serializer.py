import unittest
from typing import Literal, Set, Union
from pydantic import BaseModel

from ..graph_serializer import GraphSerializer, SerializedGraph, SerializedNode
from ..StateGraph import StateGraph
from ..StateNode import StateNode
from ..exceptions import VersionMismatchError, UnknownNodeError

class TicketNode(StateNode):
    class State(BaseModel):
        content: str = ""

    def on_notify(self):
        pass

class WeatherNode(StateNode):
    class State(BaseModel):
        weather: Union[Literal['sunny', 'rainy'], None] = None

    def on_notify(self):
        self.state().weather = 'sunny'

class FactsNode(StateNode):
    class State(BaseModel):
        facts: Set[str] = set()
        feeling: Literal['happy', 'sad', 'neutral'] = 'neutral'

    def on_notify(self):
        pass

class TestGraphSerializer(unittest.TestCase):
    def setUp(self):
        self.ticket_node = TicketNode.from_dict({'content': 'Hello, can you help me?'})
        self.weather_node = WeatherNode.from_defaults()
        self.facts_node = FactsNode.from_defaults()

        self.graph = StateGraph()
        self.graph.connect(self.ticket_node, self.facts_node)
        self.graph.connect(self.weather_node, self.facts_node)

    def test_serialize(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        self.assertIsInstance(serialized_graph, SerializedGraph)
        self.assertEqual(len(serialized_graph.nodes), 3)
        self.assertEqual(len(serialized_graph.connections), 2)

    def test_deserialize(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode}
        )

        self.assertIsInstance(deserialized_graph, StateGraph)
        self.assertEqual(len(deserialized_graph.nodes), 3)

    def test_version_mismatch(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        
        # Change the version of one node
        modified_nodes = set()
        for node in serialized_graph.nodes:
            if node.class_name == 'TicketNode':
                modified_nodes.add(node.model_copy(update={'version': '2.0.0'}))
            else:
                modified_nodes.add(node)
        
        serialized_graph.nodes = modified_nodes

        with self.assertRaises(VersionMismatchError):
            GraphSerializer.deserialize(
                serialized_graph,
                {TicketNode, WeatherNode, FactsNode}
            )

    def test_unknown_node(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        
        # Add an unknown node
        unknown_node = SerializedNode(
            id=100,
            class_name="UnknownNode",
            version="1.0.0",
            serialized_state='{"value": 0}'
        )
        serialized_graph.nodes.add(unknown_node)

        with self.assertRaises(UnknownNodeError):
            GraphSerializer.deserialize(
                serialized_graph,
                {TicketNode, WeatherNode, FactsNode}
            )

    def test_reinitialize_on_error(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        
        # Change the version of one node
        modified_nodes = set()
        for node in serialized_graph.nodes:
            if node.class_name == 'TicketNode':
                modified_nodes.add(node.model_copy(update={'version': '2.0.0'}))
            else:
                modified_nodes.add(node)
        
        serialized_graph.nodes = modified_nodes

        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode},
            reinitialize_on_error=True
        )

        self.assertIsInstance(deserialized_graph, StateGraph)
        self.assertEqual(len(deserialized_graph.nodes), 3)

if __name__ == '__main__':
    unittest.main()
