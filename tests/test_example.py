import pytest
from ..example import (
    TicketNode, WeatherNode, FactsNode, CustomStateNodeWithInitArgs,
    StateGraph, run_graph, GraphSerializer
)
from ..common import CycleDetectedError

def test_example_graph():
    # Create nodes
    ticket_node = TicketNode.from_dict({'content': 'Hello, can you help me?'})
    weather_node = WeatherNode.from_defaults()
    facts_node = FactsNode.from_defaults()
    custom_node = CustomStateNodeWithInitArgs.from_defaults({'my_argument': 'Hello'})
    
    # Create graph
    graph = StateGraph()                    \
        .connect(ticket_node, facts_node)   \
        .connect(weather_node, facts_node)  \
        .connect(weather_node, custom_node)
    
    # Notify all nodes
    graph.notify_all()
    
    # Run the graph
    run_graph(graph)
    
    # Check states
    assert ticket_node.state().content == 'Hello, can you help me?'
    assert weather_node.state().weather == 'sunny'
    assert 'User asked a question' in facts_node.state().facts
    assert facts_node.state().feeling == 'happy'
    
    # Change weather and rerun
    weather_node.state().weather = 'rainy'
    weather_node.apply_change()
    run_graph(graph)
    
    assert facts_node.state().feeling == 'sad'

def test_ticket_node():
    ticket_node = TicketNode.from_dict({'content': 'This is a statement.'})
    assert ticket_node.state().content == 'This is a statement.'

    ticket_node = TicketNode.from_defaults()
    assert ticket_node.state().content == 'Default ticket content'

def test_weather_node():
    weather_node = WeatherNode.from_defaults()
    assert weather_node.state().weather is None

    weather_node.on_notify()
    assert weather_node.state().weather == 'sunny'

def test_facts_node():
    facts_node = FactsNode.from_defaults()
    assert 'There will be facts here!' in facts_node.state().facts
    assert facts_node.state().feeling == 'neutral'

def test_custom_node():
    custom_node = CustomStateNodeWithInitArgs.from_defaults({'my_argument': 'Test'})
    assert custom_node.my_argument == 'Test'

def test_graph_serialization():
    # Create and run a graph
    ticket_node = TicketNode.from_dict({'content': 'Hello, world!'})
    weather_node = WeatherNode.from_defaults()
    facts_node = FactsNode.from_defaults()
    
    graph = StateGraph()                    \
        .connect(ticket_node, facts_node)   \
        .connect(weather_node, facts_node)
    
    graph.notify_all()
    run_graph(graph)

    # Serialize the graph
    serialized_graph = GraphSerializer.serialize(graph)

    # Deserialize the graph
    new_graph = GraphSerializer.deserialize(serialized_graph, {TicketNode, WeatherNode, FactsNode})

    # Check if the deserialized graph has the same structure and state
    assert len(new_graph.nodes) == len(graph.nodes)
    
    new_ticket_node = new_graph.get_node(TicketNode)
    new_weather_node = new_graph.get_node(WeatherNode)
    new_facts_node = new_graph.get_node(FactsNode)

    assert new_ticket_node.state().content == 'Hello, world!'
    assert new_weather_node.state().weather == 'sunny'
    assert 'User stated something' in new_facts_node.state().facts
    assert new_facts_node.state().feeling == 'happy'

def test_cycle_detection():
    node1 = TicketNode.from_defaults()
    node2 = WeatherNode.from_defaults()
    
    graph = StateGraph()
    graph.connect(node1, node2)
    
    with pytest.raises(CycleDetectedError):
        graph.connect(node2, node1)

def test_empty_graph():
    graph = StateGraph()
    assert len(graph.nodes) == 0
    assert graph.next_batch() == set()

def test_multiple_parents():
    node1 = TicketNode.from_defaults()
    node2 = WeatherNode.from_defaults()
    node3 = FactsNode.from_defaults()
    
    graph = StateGraph()
    graph.connect(node1, node3)
    graph.connect(node2, node3)
    
    assert len(node3._parents) == 2
    assert node1 in node3._parents
    assert node2 in node3._parents

def test_node_without_parents():
    node = TicketNode.from_defaults()
    graph = StateGraph()
    graph._add_node(node)
    
    graph.notify_all()
    batch = graph.next_batch()
    
    assert node in batch

def test_serialization_with_custom_node():
    ticket_node = TicketNode.from_defaults()
    custom_node = CustomStateNodeWithInitArgs.from_defaults({'my_argument': 'Test'})
    
    graph = StateGraph()
    graph.connect(ticket_node, custom_node)
    
    serialized_graph = GraphSerializer.serialize(graph)
    
    new_graph = GraphSerializer.deserialize(
        serialized_graph, 
        {TicketNode, CustomStateNodeWithInitArgs},
        node_init_args={CustomStateNodeWithInitArgs: {'my_argument': 'Test'}}
    )
    
    new_custom_node = new_graph.get_node(CustomStateNodeWithInitArgs)
    assert new_custom_node.my_argument == 'Test'

if __name__ == "__main__":
    pytest.main()
