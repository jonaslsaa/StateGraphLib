# Example usage

from typing import List, Literal, Set, Union
from pydantic import BaseModel
from .StateGraph import StateGraph
from .StateNode import StateNode

from pprint import pprint

class TicketNode(StateNode):
    class State(BaseModel):
        content: str

    def on_notify(self):
        # This node doesn't do anything on notify
        pass

class WeatherNode(StateNode):
    class State(BaseModel):
        weather: Union[Literal['sunny', 'rainy'], None] = None

    def on_notify(self):
        # Imagine a weather API call here
        self.state().weather = 'sunny'

class FactsNode(StateNode):
    class State(BaseModel):
        facts: Set[str] = set()
        feeling: Literal['happy', 'sad', 'neutral'] = 'neutral'
        
    def from_defaults():
        return FactsNode.load_from_dict({'facts': {'There will be facts here!'}})

    def on_notify(self):
        # Get content from the ticket node
        ticket_content = self.get_ancestor(TicketNode).state().content
        
        # Get weather from the weather node
        weather_node = self.get_ancestor(WeatherNode)
        
        if '?' in ticket_content:
            self.state().facts.add('User asked a question')
        else:
            self.state().facts.add('User stated something')
        
        
        weather_node.state()
            
        if weather_node.state().weather == 'sunny':
            self.state().feeling = 'happy'
        else:
            self.state().feeling = 'sad'


def run_graph(graph: StateGraph):
    it = 0
    # Get the next batch of nodes to process, these can be processed in parallel
    # We need to call next_batch after each batch is processed to get the new nodes to process
    while batch := graph.next_batch():
        print(f"  Batch {it}")
        for node in batch:
            print(f"    - Processing {node.__class__.__name__}")
            node.process()
        it += 1

if __name__ == '__main__':
    # We can create nodes with initial states
    # Let's create two root nodes, TicketNode and WeatherNode and a FactsNode derived from them
    
    # There are three ways to initialize root nodes,
    # by setting the state directly with either `load_from_dict`, 'load_from_serialized', or `from_defaults`
    
    ticket_node = TicketNode.load_from_dict({'content': 'Hello, can you help me?'})
    weather_node = WeatherNode.from_defaults()
    facts_node = FactsNode.from_defaults()
    
    # Let's see the initial state of the facts node
    pprint(facts_node.state())
    
    
    # Now let's create a graph and connect the root nodes to the child node
    graph = StateGraph()                    \
        .connect(ticket_node, facts_node)   \
        .connect(weather_node, facts_node)
    
    # As this is a new graph, we need to notify all nodes to process
    # This is because the graph is not stable yet and all nodes need to be processed
    graph.notify_all()
    
    # We can now process the graph by calling `process` on the nodes given by `next_batch`
    # `next_batch` returns a set of nodes that can be processed in parallel as they are not dependent on each other
    # `process` will notify children (mark them for processing) if the state has changed (it will also validate the state)
    run_graph(graph)
    
    # Now the graph is stable
    # Let's see the state of the facts node
    pprint(facts_node.state())

    
    # You can also manually change state outside the node, let's change the weather to rainy and process the graph again
    weather_node.state().weather = 'rainy'
    # Now we need to apply the change to the node, this will notify children and validate the state
    weather_node.apply_change() 
    # Process the graph
    run_graph(graph)
    
    pprint(facts_node.state())
    
    # We can also serialize and deserialize the nodes, this is done using the `serialize` and `load_from_serialized` methods
    # These will serialize the state of the node to a JSON string and load the state from the JSON string respectively
    # Let's try to resume a graph based on the serialized data from previous run
    serialized_ticket_node = ticket_node.serialize()
    serialized_facts_node = facts_node.serialize()
    
    ticket_node = TicketNode.load_from_serialized(serialized_ticket_node)
    facts_node = FactsNode.load_from_serialized(serialized_facts_node)
    
    # Perfect, we have the same nodes as before
    print("\n* Resumed state:")
    pprint(ticket_node.state())
    pprint(facts_node.state())