import pytest
from pydantic import BaseModel
from ..StateNode import StateNode, pydantic_deep_eq

class TestNode(StateNode):
    class State(BaseModel):
        value: int = 0

    def on_notify(self):
        self.state().value += 1

class ParentNode(StateNode):
    class State(BaseModel):
        value: str = ""

    def on_notify(self):
        self.state().value += "parent"

class ChildNode(StateNode):
    class State(BaseModel):
        value: str = ""

    def on_notify(self):
        parent = self.get_ancestor(ParentNode)
        self.state().value = parent.state().value + "_child"

def test_state_node_initialization():
    node = TestNode.from_defaults()
    assert node.state().value == 0

def test_state_node_process():
    node = TestNode.from_defaults()
    node.notify()
    node.process()
    assert node.state().value == 1

def test_state_node_serialization():
    node = TestNode.from_dict({"value": 5})
    serialized = node.serialize()
    new_node = TestNode.from_serialized(serialized)
    assert new_node.state().value == 5

def test_state_node_set_state():
    node = TestNode.from_defaults()
    node.set_state(TestNode.State(value=10))
    assert node.state().value == 10

def test_state_node_apply_change():
    node = TestNode.from_defaults()
    node.state().value = 20
    node.apply_change()
    assert node.state().value == 20

def test_state_node_get_ancestor():
    parent = ParentNode.from_defaults()
    child = ChildNode.from_defaults()
    parent._children.add(child)
    child._parents.add(parent)

    assert child.get_ancestor(ParentNode) == parent

def test_state_node_notification_propagation():
    parent = ParentNode.from_defaults()
    child = ChildNode.from_defaults()
    parent._children.add(child)
    child._parents.add(parent)

    parent.notify()
    parent.process()
    child.process()

    assert parent.state().value == "parent"
    assert child.state().value == "parent_child"

def test_pydantic_deep_eq():
    class TestModel(BaseModel):
        a: int
        b: str

    model1 = TestModel(a=1, b="test")
    model2 = TestModel(a=1, b="test")
    model3 = TestModel(a=2, b="test")

    assert pydantic_deep_eq(model1, model2)
    assert not pydantic_deep_eq(model1, model3)

def test_state_node_prev_state():
    node = TestNode.from_defaults()
    node.notify()
    node.process()
    assert node.prev_state().value == 0
    assert node.state().value == 1

def test_state_node_set_state_modes():
    class TestNodeWithChildren(StateNode):
        class State(BaseModel):
            value: int = 0

        def on_notify(self):
            pass

    parent = TestNodeWithChildren.from_defaults()
    child = TestNodeWithChildren.from_defaults()
    parent._children.add(child)
    child._parents.add(parent)

    # Test SILENT mode
    parent.set_state(TestNodeWithChildren.State(value=1), StateNode.SetStateMode.SILENT)
    assert not child._notified

    # Test NOTIFY_CHILDREN mode
    parent.set_state(TestNodeWithChildren.State(value=2), StateNode.SetStateMode.NOTIFY_CHILDREN)
    assert child._notified

    # Reset child notification
    child._notified = False

    # Test DEEP_COMPARE mode (no change)
    parent.set_state(TestNodeWithChildren.State(value=2), StateNode.SetStateMode.DEEP_COMPARE)
    assert not child._notified

    # Test DEEP_COMPARE mode (with change)
    parent.set_state(TestNodeWithChildren.State(value=3), StateNode.SetStateMode.DEEP_COMPARE)
    assert child._notified

def test_custom_state_node_with_init_args():
    node = CustomStateNodeWithInitArgs.from_defaults({'my_argument': 'Hello'})
    assert node.my_argument == 'Hello'

if __name__ == "__main__":
    pytest.main()
