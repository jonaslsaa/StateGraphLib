import pytest
from typing import Callable
from pydantic import BaseModel

from ..graph_serializer import GraphSerializer, SerializedGraph, SerializedNode
from ..StateGraph import StateGraph
from ..StateNode import StateNode
from ..exceptions import VersionMismatchError, DeserializationError, UnknownNodeError

# A simple test node for our callback tests.
class CallbackTestNode(StateNode):
    VERSION = "1.0.0"

    class State(BaseModel):
        text: str = "callback test"

    def on_notify(self):
        # For testing, do nothing.
        pass

    @classmethod
    def from_defaults(cls, node_init_args: dict = None):
        node = cls(**(node_init_args or {}))
        # When reinitialized, set a known default state.
        return node.load_from_dict({"text": "default re-init"})

# Fixture to collect callback calls.
@pytest.fixture
def callback_collector():
    """
    Provides a tuple (calls, callback) where:
      - calls is a list recording (node_id, exception) each time the callback is invoked.
      - callback is the function to be passed as on_error_callback.
    """
    calls = []
    def _callback(node_id: str, exception: Exception):
        calls.append((node_id, exception))
    return calls, _callback

def test_callback_on_version_mismatch(callback_collector):
    calls, callback = callback_collector

    # Create two nodes:
    # Node A will be the one with a version mismatch.
    node_a = CallbackTestNode.from_defaults()
    # Node B is valid.
    node_b = CallbackTestNode.from_defaults()

    # Prepare serialized nodes:
    serialized_node_a = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="2.0.0",  # Mismatch: Expected "1.0.0"
        serialized_state=node_a.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )
    serialized_node_b = SerializedNode(
        id="node-2",
        class_name="CallbackTestNode",
        version="1.0.0",  # Correct version.
        serialized_state=node_b.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    # Create a SerializedGraph with a connection: node-1 -> node-2.
    serialized_graph = SerializedGraph(
        nodes={serialized_node_a, serialized_node_b},
        connections={("node-1", "node-2")}
    )

    node_classes = {CallbackTestNode}

    # Deserialize with reinitialize_on_error=True and a callback.
    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes=node_classes,
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Verify that the callback was triggered once (for node-1).
    assert len(calls) == 1
    nid, exc = calls[0]
    assert nid == "node-1"
    assert isinstance(exc, VersionMismatchError)
    assert "Version mismatch" in str(exc)

    # Verify that the graph now contains both nodes.
    # (Since we have a connection, both nodes should be in the graph.)
    assert len(graph.nodes) == 2

    # Find node A and check that it was reinitialized.
    node_a_new = next(node for node in graph.nodes if node.serialize() == CallbackTestNode.from_defaults().serialize()) is False
    # Instead, we can inspect by checking the state value on node-1.
    # (In our reinitialization, we set "default re-init" as the text.)
    for node in graph.nodes:
        if node.__class__.__name__ == "CallbackTestNode":
            # Check if this node was the one reinitialized (its state text equals "default re-init")
            if node.serialize() == CallbackTestNode.from_defaults().serialize():
                # This is the valid node; skip.
                continue
            else:
                # For our error node, state.text should be "default re-init".
                assert node.state().text == "default re-init"
                break

def test_callback_on_deserialization_error(callback_collector):
    calls, callback = callback_collector

    # Create two nodes:
    # Node A will have invalid JSON to force a DeserializationError.
    node_a = CallbackTestNode.from_defaults()
    node_b = CallbackTestNode.from_defaults()

    serialized_node_a = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="1.0.0",  # Correct version.
        serialized_state='{"text": "some text", "extra": "??}',  # Malformed JSON.
        prev_serialized_state="",
        notified=False,
    )
    serialized_node_b = SerializedNode(
        id="node-2",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=node_b.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    # Create a SerializedGraph with a connection: node-1 -> node-2.
    serialized_graph = SerializedGraph(
        nodes={serialized_node_a, serialized_node_b},
        connections={("node-1", "node-2")}
    )

    node_classes = {CallbackTestNode}

    # Deserialize with reinitialize_on_error=True; callback should be triggered.
    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes=node_classes,
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Verify that the callback was triggered for node-1.
    assert len(calls) == 1
    nid, exc = calls[0]
    assert nid == "node-1"
    assert isinstance(exc, DeserializationError)

    # Verify that both nodes are present.
    assert len(graph.nodes) == 2

    # Verify that node-1 (error node) was reinitialized.
    # We expect its state text to equal "default re-init".
    for node in graph.nodes:
        if node.serialize() == CallbackTestNode.from_defaults().serialize():
            # This is the valid node.
            continue
        else:
            assert node.state().text == "default re-init"
            break

def test_no_callback_if_error_not_reinitialized():
    # If reinitialize_on_error is False, the error should be raised and no callback is invoked.
    node = CallbackTestNode.from_defaults()
    serialized_node = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="2.0.0",  # Mismatch.
        serialized_state=node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )
    # Also include a valid node so a connection exists.
    valid_node = CallbackTestNode.from_defaults()
    serialized_node_valid = SerializedNode(
        id="node-2",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=valid_node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    serialized_graph = SerializedGraph(
        nodes={serialized_node, serialized_node_valid},
        connections={("node-1", "node-2")}
    )

    with pytest.raises(VersionMismatchError):
        GraphSerializer.deserialize(
            serialized_graph,
            node_classes={CallbackTestNode},
            node_init_args={},
            reinitialize_on_error=False,
            on_error_callback=None
        )

def test_callback_for_unknown_node(callback_collector):
    calls, callback = callback_collector

    # Create a valid node for connection.
    node = CallbackTestNode.from_defaults()
    serialized_node = SerializedNode(
        id="node-1",
        class_name="NonExistentNode",  # Unknown class.
        version="1.0.0",
        serialized_state=node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )
    # Also add a valid node.
    valid_node = CallbackTestNode.from_defaults()
    serialized_node_valid = SerializedNode(
        id="node-2",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=valid_node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    serialized_graph = SerializedGraph(
        nodes={serialized_node, serialized_node_valid},
        connections={("node-1", "node-2")}
    )

    with pytest.raises(UnknownNodeError):
        GraphSerializer.deserialize(
            serialized_graph,
            node_classes={CallbackTestNode},
            reinitialize_on_error=True,
            on_error_callback=callback
        )

    # The callback should not be triggered for unknown node errors.
    assert len(calls) == 0

def test_multiple_errors_in_single_graph(callback_collector):
    calls, callback = callback_collector
    node_classes = {CallbackTestNode}

    # Create serialized graph with multiple error types
    serialized_nodes = [
        # Version mismatch
        SerializedNode(
            id="node-1",
            class_name="CallbackTestNode",
            version="2.0.0",
            serialized_state=CallbackTestNode().state().model_dump_json(),
            prev_serialized_state="",
            notified=False,
        ),
        # Invalid JSON
        SerializedNode(
            id="node-2",
            class_name="CallbackTestNode",
            version="1.0.0",
            serialized_state='{"text": "invalid...',
            prev_serialized_state="",
            notified=False,
        ),
        # Valid node
        SerializedNode(
            id="node-3",
            class_name="CallbackTestNode",
            version="1.0.0",
            serialized_state=CallbackTestNode().state().model_dump_json(),
            prev_serialized_state="",
            notified=False,
        )
    ]

    serialized_graph = SerializedGraph(
        nodes=set(serialized_nodes),
        connections={("node-1", "node-3"), ("node-2", "node-3")}
    )

    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes=node_classes,
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Verify two error callbacks
    assert len(calls) == 2
    error_ids = {nid for nid, _ in calls}
    assert error_ids == {"node-1", "node-2"}

    # Verify all three nodes exist (two reinitialized, one valid)
    assert len(graph.nodes) == 3
    states = [n.state().text for n in graph.nodes]
    assert set(states) == {"default re-init", "callback test"}

def test_callback_on_init_args_error(callback_collector):
    calls, callback = callback_collector

    class InitArgNode(CallbackTestNode):
        def __init__(self, required_arg: str):
            super().__init__()
            self.required_arg = required_arg

        @classmethod
        def from_defaults(cls, node_init_args: dict = None):
            return cls(**node_init_args).load_from_dict({"text": "init-arg-default"})

    serialized_node = SerializedNode(
        id="node-1",
        class_name="InitArgNode",
        version="1.0.0",
        serialized_state=InitArgNode("good").state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    # Deserialize without required init args
    with pytest.raises(TypeError):
        GraphSerializer.deserialize(
            SerializedGraph(nodes={serialized_node}, connections=set()),
            node_classes={InitArgNode},
            node_init_args={},  # Missing required_arg
            reinitialize_on_error=False
        )

    # Now test with reinitialize_on_error=True
    graph = GraphSerializer.deserialize(
        SerializedGraph(nodes={serialized_node}, connections=set()),
        node_classes={InitArgNode},
        node_init_args={InitArgNode: {"required_arg": "fixed"}},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Should have 1 error from failed initial deserialization attempt
    assert len(calls) == 1
    nid, exc = calls[0]
    assert nid == "node-1"
    assert isinstance(exc, DeserializationError)

    # Node should be reinitialized with correct args
    node = next(iter(graph.nodes))
    assert node.required_arg == "fixed"
    assert node.state().text == "init-arg-default"

def test_callback_on_prev_state_error(callback_collector):
    calls, callback = callback_collector
    node_classes = {CallbackTestNode}

    # Create node with valid current state but invalid previous state
    valid_state = CallbackTestNode().state().model_dump_json()
    serialized_node = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=valid_state,
        prev_serialized_state='{"text": 123}',  # Invalid type for text
        notified=False,
    )

    graph = GraphSerializer.deserialize(
        SerializedGraph(nodes={serialized_node}, connections=set()),
        node_classes=node_classes,
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Should have 1 error from prev state deserialization
    assert len(calls) == 1
    nid, exc = calls[0]
    assert nid == "node-1"
    assert isinstance(exc, DeserializationError)

    # Node should have current state from serialized data
    node = next(iter(graph.nodes))
    assert node.state().text == "callback test"
    
    # Prev state should be reset to current state after reinitialization
    assert node.prev_state().text == "callback test"

def test_callback_not_triggered_on_valid_graph(callback_collector):
    calls, callback = callback_collector
    
    # Create valid nodes
    valid_node = CallbackTestNode.from_defaults()
    serialized_node = SerializedNode(
        id="valid-node",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=valid_node.state().model_dump_json(),
        prev_serialized_state=valid_node.prev_state().model_dump_json(),
        notified=False
    )
    
    # Create valid graph
    valid_graph = SerializedGraph(
        nodes={serialized_node},
        connections=set()
    )
    
    # Deserialize with error handling enabled
    GraphSerializer.deserialize(
        valid_graph,
        node_classes={CallbackTestNode},
        reinitialize_on_error=True,
        on_error_callback=callback
    )
    
    # Verify no errors were recorded
    assert len(calls) == 0

if __name__ == "__main__":
    pytest.main()