import unittest
from typing import Literal, Set, Union
from pydantic import BaseModel

from ..graph_serializer import GraphSerializer, SerializedGraph, SerializedNode
from ..StateGraph import StateGraph
from ..StateNode import StateNode
from ..exceptions import VersionMismatchError, UnknownNodeError
from ..example import CustomStateNodeWithInitArgs

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

    def test_notified_serialization(self):
        # Notify all nodes
        self.graph.notify_all()
        
        serialized_graph = GraphSerializer.serialize(self.graph)
        
        # Check if all nodes are marked as notified in the serialized graph
        for node in serialized_graph.nodes:
            self.assertTrue(node.notified, f"Node {node.id} is not marked as notified")
        
        # Deserialize the graph
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode}
        )
        
        # Check if all nodes are still marked as notified in the deserialized graph
        for node in deserialized_graph.nodes:
            self.assertTrue(node._notified, f"Node {type(node).__name__} after deserialization is not notified")

    def test_prev_state_serialization(self):
        ticket_node = self.graph.get_node(TicketNode)
        # Assert ticket node content
        self.assertEqual(ticket_node.state().content, 'Hello, can you help me?')
        # Change the state of a node to create a prev_state
        ticket_node.state().content = "Updated content"
        did_change = ticket_node.apply_change()
        self.assertTrue(did_change)
        self.assertEqual(ticket_node.state().content, "Updated content")
        self.assertEqual(ticket_node._prev_state.content, "Hello, can you help me?")
        # Process the node
        ticket_node.notify()
        ticket_node.process() # Previous state is set here
    
        serialized_graph = GraphSerializer.serialize(self.graph)
        
        # Find the serialized ticket node
        serialized_ticket_node = next(node for node in serialized_graph.nodes if node.class_name == ticket_node.__class__.__name__)
        
        # Check if prev_serialized_state is not empty
        self.assertNotEqual(serialized_ticket_node.prev_serialized_state, "")
        
        # Deserialize the graph
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode}
        )
        
        # Find the deserialized ticket node
        deserialized_ticket_node = deserialized_graph.get_node(TicketNode)
        
        # Check if prev_state is correctly deserialized
        self.assertIsNotNone(deserialized_ticket_node._prev_state)
        self.assertEqual(deserialized_ticket_node._prev_state.content, "Hello, can you help me?", "Prev state is not correctly deserialized")

    def test_serialize_deserialize_with_custom_node(self):
        custom_node = CustomStateNodeWithInitArgs.from_defaults({'my_argument': 'Test'})
        self.graph.connect(self.ticket_node, custom_node)

        serialized_graph = GraphSerializer.serialize(self.graph)
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode, CustomStateNodeWithInitArgs},
            node_init_args={CustomStateNodeWithInitArgs: {'my_argument': 'Test'}}
        )

        self.assertEqual(len(deserialized_graph.nodes), 4)
        custom_node_deserialized = next(node for node in deserialized_graph.nodes if isinstance(node, CustomStateNodeWithInitArgs))
        self.assertEqual(custom_node_deserialized.my_argument, 'Test')

    def test_serialize_deserialize_with_changed_state(self):
        self.ticket_node.state().content = "Updated content"
        self.ticket_node.apply_change()
        self.weather_node.state().weather = 'rainy'
        self.weather_node.apply_change()

        serialized_graph = GraphSerializer.serialize(self.graph)
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode}
        )

        deserialized_ticket_node = next(node for node in deserialized_graph.nodes if isinstance(node, TicketNode))
        deserialized_weather_node = next(node for node in deserialized_graph.nodes if isinstance(node, WeatherNode))

        self.assertEqual(deserialized_ticket_node.state().content, "Updated content")
        self.assertEqual(deserialized_weather_node.state().weather, 'rainy')

    def test_serialize_deserialize_preserves_connections(self):
        serialized_graph = GraphSerializer.serialize(self.graph)
        deserialized_graph = GraphSerializer.deserialize(
            serialized_graph,
            {TicketNode, WeatherNode, FactsNode}
        )

        deserialized_facts_node = next(node for node in deserialized_graph.nodes if isinstance(node, FactsNode))
        self.assertEqual(len(deserialized_facts_node._parents), 2)
        self.assertTrue(any(isinstance(parent, TicketNode) for parent in deserialized_facts_node._parents))
        self.assertTrue(any(isinstance(parent, WeatherNode) for parent in deserialized_facts_node._parents))

if __name__ == '__main__':
    unittest.main()
