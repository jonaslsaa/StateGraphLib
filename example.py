# Example usage

from typing import List, Literal, Set, Union
from pydantic import BaseModel
from StateGraph import StateGraph
from StateNode import StateNode


class TicketNode(StateNode):
    class State(BaseModel):
        content: str

    def on_notify(self):
        # This node doesn't do anything on notify, onl
        self.notify_children() # Notify children to process

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


from pprint import pprint

def run_graph(graph: StateGraph):
    it = 0
    while batch := graph.next_batch():
        print(f"  Batch {it}")
        for node in batch:
            print(f"    - Processing {node.__class__.__name__}")
            node.process()
        it += 1

if __name__ == '__main__':
    # Create a graph and process it
    # Ticket node and Weather node are the roots
    # Facts node is the child
    
    # There three ways to initialize root nodes, by setting the state directly with either `load_from_dict`, 'load_from_serialized', or `from_defaults`
    ticket_node = TicketNode.load_from_dict({'content': 'Hello, can you help me?'})
    weather_node = WeatherNode.from_defaults()
    facts_node = FactsNode.from_defaults()
    
    print("* Initial state:")
    pprint(facts_node.state())
    
    print("\n* Initializing graph")
    # Let's create a graph and connect the root nodes to the child node
    graph = StateGraph()                    \
        .connect(ticket_node, facts_node)   \
        .connect(weather_node, facts_node)
    
    # As this is a new graph, we need to notify all nodes
    graph.notify_all()
    
    
    print("\n* Processing graph")
    # Process the graph
    run_graph(graph)
    
    # Now the graph is stable
    
    print("\n* After processing:")
    pprint(facts_node.state())

    
    # Now,
    # Let's manually change the weather to rainy and process the graph again
    weather_node.state().weather = 'rainy'
    print("\n* Weather changed to rainy")
    # Notify children that their parent has a changed state
    weather_node.notify_children() 
    # Process the graph
    run_graph(graph)
    
    print("\n* After processing:")
    pprint(facts_node.state())
    
    # Now,
    # Let's try to resume a graph based on the serialized data from previous run
    serialized_ticket_node = ticket_node.serialize()
    serialized_facts_node = facts_node.serialize()
    
    ticket_node = TicketNode.load_from_serialized(serialized_ticket_node)
    facts_node = FactsNode.load_from_serialized(serialized_facts_node)
    
    print("\n* Resumed state:")
    pprint(ticket_node.state())
    pprint(facts_node.state())