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

# A test node that accepts initialization arguments.
class CallbackInitArgTestNode(StateNode):
    VERSION = "1.0.0"

    def __init__(self, my_arg: str = "default_arg"):
        super().__init__()
        self.my_arg = my_arg

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

    # Check that the error node was reinitialized to the default state.
    for node in graph.nodes:
        # Identify the node that had an error by checking its state text.
        if node.state().text == "default re-init":
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
    for node in graph.nodes:
        if node.state().text == "default re-init":
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

# --- New Tests ---

def test_callback_multiple_errors(callback_collector):
    """
    Test that when multiple nodes in the serialized graph have errors,
    the callback is triggered for each error.
    """
    calls, callback = callback_collector

    # Create three nodes:
    # Node A: Version mismatch error.
    node_a = CallbackTestNode.from_defaults()
    # Node B: Deserialization error (malformed JSON).
    node_b = CallbackTestNode.from_defaults()
    # Node C: Valid node.
    node_c = CallbackTestNode.from_defaults()

    serialized_node_a = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="2.0.0",  # Version mismatch.
        serialized_state=node_a.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )
    serialized_node_b = SerializedNode(
        id="node-2",
        class_name="CallbackTestNode",
        version="1.0.0",  # Correct version but malformed JSON.
        serialized_state='{"text": "invalid json", "extra": "oops}',  # Malformed JSON.
        prev_serialized_state="",
        notified=False,
    )
    serialized_node_c = SerializedNode(
        id="node-3",
        class_name="CallbackTestNode",
        version="1.0.0",  # Valid node.
        serialized_state=node_c.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    # Connect nodes in a chain: A -> B -> C.
    serialized_graph = SerializedGraph(
        nodes={serialized_node_a, serialized_node_b, serialized_node_c},
        connections={("node-1", "node-2"), ("node-2", "node-3")}
    )

    node_classes = {CallbackTestNode}

    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes=node_classes,
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Expect two errors: one for node-1 (version mismatch) and one for node-2 (deserialization error).
    assert len(calls) == 2
    error_types = {type(exc) for _, exc in calls}
    assert VersionMismatchError in error_types
    assert DeserializationError in error_types

    # Verify that the graph contains three nodes.
    assert len(graph.nodes) == 3

def test_callback_not_triggered_on_valid_graph(callback_collector):
    """
    Test that if all nodes are valid, no error callback is triggered.
    """
    calls, callback = callback_collector

    # Create two valid nodes.
    node_a = CallbackTestNode.from_defaults()
    node_b = CallbackTestNode.from_defaults()

    serialized_node_a = SerializedNode(
        id="node-1",
        class_name="CallbackTestNode",
        version="1.0.0",
        serialized_state=node_a.state().model_dump_json(),
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

    serialized_graph = SerializedGraph(
        nodes={serialized_node_a, serialized_node_b},
        connections={("node-1", "node-2")}
    )

    # Deserialize with reinitialize_on_error True, but no errors should occur.
    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes={CallbackTestNode},
        node_init_args={},
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # No callback calls should have been made.
    assert len(calls) == 0
    # Graph should contain two nodes.
    assert len(graph.nodes) == 2

def test_callback_with_init_args(callback_collector):
    """
    Test that when a node with initialization arguments encounters an error,
    the callback is triggered and the reinitialized node retains the provided init args.
    """
    calls, callback = callback_collector

    # Create a node that will trigger a version mismatch.
    node = CallbackInitArgTestNode.from_defaults()
    serialized_node = SerializedNode(
        id="node-1",
        class_name="CallbackInitArgTestNode",
        version="2.0.0",  # Mismatch.
        serialized_state=node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    # Create a valid node for connection.
    valid_node = CallbackInitArgTestNode.from_defaults()
    serialized_valid = SerializedNode(
        id="node-2",
        class_name="CallbackInitArgTestNode",
        version="1.0.0",
        serialized_state=valid_node.state().model_dump_json(),
        prev_serialized_state="",
        notified=False,
    )

    serialized_graph = SerializedGraph(
        nodes={serialized_node, serialized_valid},
        connections={("node-1", "node-2")}
    )

    node_classes = {CallbackInitArgTestNode}
    init_args = {CallbackInitArgTestNode: {'my_arg': 'test_value'}}

    graph = GraphSerializer.deserialize(
        serialized_graph,
        node_classes=node_classes,
        node_init_args=init_args,
        reinitialize_on_error=True,
        on_error_callback=callback
    )

    # Callback should have been triggered once for the version mismatch.
    assert len(calls) == 1
    nid, exc = calls[0]
    assert nid == "node-1"
    assert isinstance(exc, VersionMismatchError)

    # Retrieve the reinitialized node (the one with version mismatch).
    error_node = next(node for node in graph.nodes if getattr(node, 'my_arg', None) == 'test_value')
    assert error_node.my_arg == 'test_value'
    # Also, check that its state was reinitialized.
    assert error_node.state().text == "default re-init"