# Example usage

from typing import List, Literal
from pydantic import BaseModel
from StateGraph import StateGraph
from StateNode import StateNode


class TicketNode(StateNode):
    class State(BaseModel):
        content: str

    def process(self):
        self.notify_children()

class WeatherNode(StateNode):
    class State(BaseModel):
        weather: Literal['sunny', 'rainy']

    def process(self):
        self.state.weather = 'sunny'

class FactsNode(StateNode):
    class State(BaseModel):
        facts: List[str] = []
        feeling: Literal['happy', 'sad', 'neutral'] = 'neutral'

    def process(self):
        # Get content from the ticket node
        ticket_content = self.get_ancestor(TicketNode).state.content
        
        # Get weather from the weather node
        weather_node = self.get_ancestor(WeatherNode)
        
        print(f"  Ticket content: {ticket_content}")
        print(f"  Weather: {weather_node.state.weather}")
        
        if '?' in ticket_content:
            self.state.facts += ['User asked a question']
        else:
            self.state.facts += ['User stated something']
            
        if weather_node.state.weather == 'sunny':
            self.state.feeling = 'happy'
        else:
            self.state.feeling = 'sad'


from pprint import pprint
if __name__ == '__main__':
    # Create a graph and process it
    ticket_node = TicketNode.load_from_dict({'content': 'Hello, can you help me? :)'})
    weather_node = WeatherNode.load_from_dict({'weather': 'sunny'})
    facts_node = FactsNode.load_from_dict({})
    
    print("* Roots state:")
    pprint(ticket_node.serialize())
    pprint(weather_node.serialize())
    
    print("* Initial state:")
    pprint(facts_node.serialize())
    
    print("\n* Initializing and processing the graph:")
    graph = StateGraph()                    \
        .mark_as_roots([ticket_node, weather_node])         \
        .connect(ticket_node, facts_node)   \
        .connect(weather_node, facts_node)  \
        .notify_roots()                     \
        .process()
    
    print("\n* After processing:")
    pprint(facts_node.serialize())
    
    # Now,
    # Let's change the weather to rainy and process the graph again
    weather_node.state.weather = 'rainy'
    print("\n* Weather changed to rainy")
    weather_node.notify_children()
    graph.process()
    
    print("\n* After processing:")
    pprint(facts_node.serialize())
    
    # Now,
    # Try to resume a graph based on the serialized data from previous run
    serialized_ticket_node = ticket_node.serialize()
    serialized_facts_node = facts_node.serialize()
    
    ticket_node = TicketNode.load_from_serialized(serialized_ticket_node)
    facts_node = FactsNode.load_from_serialized(serialized_facts_node)
    
    print("\n* Resumed state:")
    pprint(ticket_node.serialize())
    pprint(facts_node.serialize())