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

if __name__ == "__main__":
    pytest.main()
