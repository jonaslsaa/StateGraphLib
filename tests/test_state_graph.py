import pytest
from pydantic import BaseModel
from ..StateGraph import StateGraph, StateNode, CycleDetectedError

def create_test_node():
    class TestNode(StateNode):
        class State(BaseModel):
            value: int = 0

        def on_notify(self):
            pass

    return TestNode

def test_state_graph_initialization():
    graph = StateGraph()
    assert len(graph.nodes) == 0

def test_add_node():
    TestNode = create_test_node()
    graph = StateGraph()
    node = TestNode.from_defaults()
    graph._add_node(node)
    assert len(graph.nodes) == 1
    assert node in graph.nodes

def test_connect_nodes():
    TestNode = create_test_node()
    graph = StateGraph()
    parent = TestNode.from_defaults()
    child = TestNode.from_defaults()
    graph.connect(parent, child)
    assert child in parent._children
    assert parent in child._parents
    assert len(graph.nodes) == 2

def test_connect_nodes_cycle_detection():
    TestNode = create_test_node()
    graph = StateGraph()
    node1 = TestNode.from_defaults()
    node2 = TestNode.from_defaults()
    node3 = TestNode.from_defaults()
    
    graph.connect(node1, node2)
    graph.connect(node2, node3)
    
    with pytest.raises(CycleDetectedError):
        graph.connect(node3, node1)

def test_connect_nodes_allow_cycle():
    TestNode = create_test_node()
    graph = StateGraph()
    node1 = TestNode.from_defaults()
    node2 = TestNode.from_defaults()
    
    graph.connect(node1, node2)
    graph.connect(node2, node1, allow_cycle=True)
    
    assert node2 in node1._children
    assert node1 in node2._children

def test_notify_all():
    TestNode = create_test_node()
    class NotifyTestNode(TestNode):
        class State(BaseModel):
            value: int = 0

        def on_notify(self):
            self.state().value += 1

    graph = StateGraph()
    node1 = NotifyTestNode.from_defaults()
    node2 = NotifyTestNode.from_defaults()
    
    graph.connect(node1, node2)
    graph.notify_all()
    
    assert node1._notified
    assert node2._notified

def test_get_node():
    TestNode = create_test_node()
    graph = StateGraph()
    node1 = TestNode.from_defaults()
    node2 = TestNode.from_defaults()
    
    graph.connect(node1, node2)
    
    assert graph.get_node(TestNode) in [node1, node2]

def test_get_nodes():
    TestNode = create_test_node()
    graph = StateGraph()
    node1 = TestNode.from_defaults()
    node2 = TestNode.from_defaults()
    
    graph.connect(node1, node2)
    
    assert set(graph.get_nodes(TestNode)) == {node1, node2}

def test_next_batch():
    TestNode = create_test_node()
    class BatchTestNode(TestNode):
        class State(BaseModel):
            value: int = 0

        def on_notify(self):
            self.state().value += 1

    graph = StateGraph()
    root = BatchTestNode.from_defaults()
    child1 = BatchTestNode.from_defaults()
    child2 = BatchTestNode.from_defaults()
    grandchild = BatchTestNode.from_defaults()
    
    graph.connect(root, child1)
    graph.connect(root, child2)
    graph.connect(child1, grandchild)
    
    graph.notify_all()
    
    batch = graph.next_batch()
    assert batch == {root}
    
    for node in batch:
        node.process()
    
    batch = graph.next_batch()
    assert batch == {child1, child2}

def test_empty_graph():
    graph = StateGraph()
    assert len(graph.nodes) == 0
    assert graph.next_batch() == set()

def test_single_node_graph():
    TestNode = create_test_node()
    graph = StateGraph()
    node = TestNode.from_defaults()
    graph._add_node(node)
    assert len(graph.nodes) == 1
    graph.notify_all()
    assert graph.next_batch() == {node}

def test_complex_hierarchy():
    TestNode = create_test_node()
    graph = StateGraph()
    root = TestNode.from_defaults()
    child1 = TestNode.from_defaults()
    child2 = TestNode.from_defaults()
    grandchild1 = TestNode.from_defaults()
    grandchild2 = TestNode.from_defaults()

    graph.connect(root, child1)
    graph.connect(root, child2)
    graph.connect(child1, grandchild1)
    graph.connect(child2, grandchild2)

    graph.notify_all()
    assert graph.next_batch() == {root}
    
    for node in graph.next_batch():
        node.process()
    
    assert graph.next_batch() == {child1, child2}

def test_error_conditions():
    TestNode = create_test_node()
    graph = StateGraph()
    node1 = TestNode.from_defaults()
    node2 = TestNode.from_defaults()

    # Test connecting a node to itself
    with pytest.raises(AssertionError):
        graph.connect(node1, node1)

    # Test connecting the same nodes twice
    graph.connect(node1, node2)
    graph.connect(node1, node2)  # This should not raise an error, but also should not create a duplicate connection
    assert len(node1._children) == 1
    assert len(node2._parents) == 1

    # Test getting a non-existent node type
    class NonExistentNode(StateNode):
        pass

    assert graph.get_node(NonExistentNode) is None
    assert graph.get_nodes(NonExistentNode) == []

if __name__ == "__main__":
    pytest.main()
