import pytest
from ..example import (
    TicketNode, WeatherNode, FactsNode, CustomStateNodeWithInitArgs,
    StateGraph, run_graph
)

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

if __name__ == "__main__":
    pytest.main()
