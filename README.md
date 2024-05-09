# StateGraphLib

StateGraphLib is a minimalistic Python library that manages and processes stateful nodes within a directed acyclic graph (DAG). It is particularly useful for AI Large Language Model (LLM) generation tasks and other scenarios where the state of a node depends on the states of its ancestor nodes. The library allows for updating node states through external services or AI models, which can be integrated within the node's processing logic.

## Features

- **Stateful Nodes**: Each node in the graph maintains its own state, which can be updated based on the node's logic. This automatically informs its children.
- **Directed Acyclic Graph**: Nodes can be connected in a parent-child relationship, forming a DAG representing dependencies.
- **Layered Processing**: Nodes are processed in layers based on their dependencies, ensuring that parent states are updated before their children.
- **Serialization/Deserialization**: Nodes can be serialized to JSON and deserialized back to their original state, making it easy to store and resume state.
- **Explicit Cycles**: The library includes cycle detection to prevent the creation of cycles within the graph.
- **Typed State**: Use Pydantic models to define the state of each node, providing type safety and validation.

## Usage

Below is an example of how to use StateGraphLib to create a graph with three types of nodes: `TicketNode`, `WeatherNode`, and `FactsNode`. Each node type has its own state and processing logic.

```python
from typing import List, Literal, Set, Union
from pydantic import BaseModel
from StateGraph import StateGraph
from StateNode import StateNode
from pprint import pprint

# Define our node classes with custom processing logic
class TicketNode(StateNode):
    class State(BaseModel):
        content: str

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
        feeling: Literal['happy', 'sad', 'neutral'] = 'neutral' # You can define a default like this
        
    @staticmethod
    def from_defaults():                                        # ... or like this.
        return FactsNode.load_from_dict({'facts': {'There will be facts here!'}})

    def on_notify(self):
        ticket_content = self.get_ancestor(TicketNode).state().content
        weather_node = self.get_ancestor(WeatherNode)
        self.state().facts.add('User asked a question' if '?' in ticket_content else 'User stated something')
        self.state().feeling = 'happy' if weather_node.state().weather == 'sunny' else 'sad'

# Initialize nodes
ticket_node = TicketNode.load_from_dict({'content': 'Hello, can you help me?'})
weather_node = WeatherNode.from_defaults()
facts_node = FactsNode.from_defaults()

# Create the graph and connect nodes
graph = StateGraph() \
    .connect(ticket_node, facts_node) \
    .connect(weather_node, facts_node)

# Notify all nodes to process since the graph is completely new.
graph.notify_all()

# Define a simple graph runner.
def run_graph(graph: StateGraph):
    # Get the next batch of nodes to process, these can be processed in parallel
    # We need to call next_batch after each batch is processed to get the new nodes to process
    while batch := graph.next_batch():
        for node in batch:
            node.process()

# Run the graph processing
run_graph(graph)

# Serialize and deserialize node state
serialized_ticket_node = ticket_node.serialize()
ticket_node = TicketNode.load_from_serialized(serialized_ticket_node)

# Output the resumed state
print("\n* Resumed state:")
pprint(ticket_node.state())
pprint(facts_node.state())
```

See the [example.py](example.py) file for a complete example with additional comments.
