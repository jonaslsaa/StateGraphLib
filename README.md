# StateGraphLib

StateGraphLib is a Python library designed to manage and process stateful nodes within a directed acyclic graph (DAG). It is particularly useful for AI Large Language Model (LLM) generation tasks and other scenarios where the state of a node depends on the states of its ancestor nodes. The library allows for updating node states through external services or AI models, which can be integrated within the node's processing logic.

## Features

- **Stateful Nodes**: Each node in the graph maintains its own state, which can be updated based on the node's logic.
- **Directed Acyclic Graph**: Nodes can be connected in a parent-child relationship, forming a DAG to represent dependencies.
- **Serialization/Deserialization**: Nodes can be serialized to JSON and deserialized back to their original state, making it easy to store and resume state.
- **Custom Processing Logic**: Implement custom processing logic within nodes that can interact with AI LLMs or other services.
- **Cycle Detection**: The library includes cycle detection to prevent the creation of cycles within the graph.
- **Layered Processing**: Nodes are processed in layers based on their dependencies, ensuring that parent states are updated before their children.
- **Root Node Notification**: The graph can notify root nodes to start processing, triggering the processing of all connected nodes.
- **Type Annotations**: Use Pydantic models to define the state of each node, providing type safety and validation.

## Usage

Below is an example of how to use StateGraphLib to create a graph with three types of nodes: `TicketNode`, `WeatherNode`, and `FactsNode`. Each node type has its own state and processing logic.

```python
from stategraphlib import StateNode, StateGraph
from pydantic import BaseModel
from typing import List, Literal

# Define your node classes with custom processing logic
class TicketNode(StateNode):
    class State(BaseModel):
        content: str

    def process(self):
        # Custom logic to update the node's state
        self.notify_children()

class WeatherNode(StateNode):
    class State(BaseModel):
        weather: Literal['sunny', 'rainy']

    def process(self):
        # Custom logic to update the node's state
        self.state.weather = 'sunny'

class FactsNode(StateNode):
    class State(BaseModel):
        facts: List[str] = []
        feeling: Literal['happy', 'sad', 'neutral'] = 'neutral'

    def process(self):
        # Custom logic to update the node's state based on ancestor states
        ticket_content = self.get_ancestor(TicketNode).state.content
        weather_node = self.get_ancestor(WeatherNode)
        # ... additional processing logic ...

# Create and connect nodes
ticket_node = TicketNode.load_from_dict({'content': 'Hello, can you help me? :)'})
weather_node = WeatherNode.load_from_dict({'weather': 'sunny'})
facts_node = FactsNode.load_from_dict({})

# Initialize the graph
graph = StateGraph() \
    # Mark nodes as roots and connect them
    .mark_as_roots([ticket_node, weather_node]) \
    .connect(ticket_node, facts_node) \
    .connect(weather_node, facts_node) \
    # Manually notify roots that they have new data,
    # which triggers processing and notification to children
    .notify_roots() \
    # Process all nodes in the graph (layer-wise)
    .process()

# Serialize node state
serialized_facts_node = facts_node.serialize()

# Deserialize node state
facts_node = FactsNode.load_from_serialized(serialized_facts_node)
```
