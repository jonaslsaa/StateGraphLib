import pytest
from pydantic import BaseModel, ValidationError
from ..StateNode import StateNode, pydantic_deep_eq
from ..example import CustomStateNodeWithInitArgs

def create_test_node_class():
    class TestNode(StateNode):
        class State(BaseModel):
            value: int = 0

        def on_notify(self):
            self.state().value += 1

        @classmethod
        def from_defaults(cls):
            return cls().load_from_dict({"value": 0})
    
    return TestNode

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
    TestNode = create_test_node_class()
    node = TestNode.from_defaults()
    assert node.state().value == 0

def test_state_node_process():
    TestNode = create_test_node_class()
    node = TestNode.from_defaults()
    node.notify()
    node.process()
    assert node.state().value == 1

def test_state_node_serialization():
    TestNode = create_test_node_class()
    node = TestNode.from_dict({"value": 5})
    serialized = node.serialize()
    new_node = TestNode.from_serialized(serialized)
    assert new_node.state().value == 5

def test_state_node_set_state():
    TestNode = create_test_node_class()
    node = TestNode.from_defaults()
    node.set_state(TestNode.State(value=10))
    assert node.state().value == 10

def test_state_node_apply_change():
    TestNode = create_test_node_class()
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
    TestNode = create_test_node_class()
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
    node = CustomStateNodeWithInitArgs.from_defaults(node_init_args={'my_argument': 'Hello'})
    assert node.my_argument == 'Hello'

def test_custom_state_node_without_defaults():
    class CustomNode(StateNode):
        class State(BaseModel):
            required_value: int
            optional_value: str = "default"

        def on_notify(self):
            pass

    # Test initialization with all required values
    node = CustomNode.from_dict({"required_value": 42})
    assert node.state().required_value == 42
    assert node.state().optional_value == "default"

    # Test initialization with all values
    node = CustomNode.from_dict({"required_value": 42, "optional_value": "custom"})
    assert node.state().required_value == 42
    assert node.state().optional_value == "custom"

    # Test initialization without required value (should raise an error)
    with pytest.raises(ValidationError):
        CustomNode.from_dict({})

if __name__ == "__main__":
    pytest.main()
