from typing import Any, List, Dict, Union, Set
from pydantic import BaseModel
import json

class MutationValue(BaseModel):
    value: str
    type_name: str  # Supports JSON serializable types (int, str, bool, list, dict) and also Sets, BaseModel is also supported
    schema: Union[Dict[str, Any], None] = None # Optional schema to validate the new value (must be a Pydantic model)

class StateMutation(BaseModel):
    path: List[str]  # Path to the value that was changed, within model
    old_value: MutationValue
    new_value: MutationValue

def _serialize(value: Any) -> str:
    '''
    Serialize a value to a string.
    '''
    if isinstance(value, set):
        return json.dumps(list(value))
    if isinstance(value, frozenset):
        return json.dumps(list(value))
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value)

def _deserialize(value: str, python_type: str, schema_json: str = None) -> Any:
    '''
    Deserialize a string to a value.
    '''
    if python_type == 'set':
        return set(json.loads(value))
    if python_type == 'frozenset':
        return frozenset(json.loads(value))
    if python_type == 'BaseModel':
        raise ValueError("BaseModel deserialization is not supported")
        assert schema_json is not None, "schema_json is required for BaseModel deserialization"
        return schema_json.model_load_json(value)
    return json.loads(value)

def _create_mutation_value(value: Any) -> MutationValue:
    '''
    Create a MutationValue object from a value.
    '''
    schema = None
    if isinstance(value, BaseModel):
        # Get classes schema
        schema = value.__class__.model_json_schema(mode='serialization')
        print('schema', schema)
    return MutationValue(
        value=_serialize(value),
        type_name=type(value).__name__,
        schema=schema
    )

def apply_mutation(old_value: BaseModel, mutation: StateMutation, ignore_old_value=False):
    '''
    Apply a mutation to a model.
    '''
    # Traverse to the parent of the attribute to change
    value = old_value
    try:
        for p in mutation.path[:-1]:
            value = getattr(value, p)
    except AttributeError:
        raise AttributeError(f"Path {mutation.path} not found in the model")
    
    # Apply the mutation
    current_value = getattr(value, mutation.path[-1])
    
    # Check if the old value matches the current value (optional)
    if not ignore_old_value and _serialize(current_value) != mutation.old_value.value:
        raise ValueError(f"Old value {mutation.old_value.value} does not match the current value {current_value}")
    
    # Set the new value
    setattr(value, mutation.path[-1], _deserialize(mutation.new_value.value, mutation.new_value.type_name))
    
    return old_value  # Return the modified model

def get_mutations(old_model: BaseModel, new_model: BaseModel, path: List[str] = []):
    '''
    Get the mutations that need to be applied to old_model to get to new_model.
    '''
    mutations = []
    for field in new_model.model_fields:
        new_value = getattr(new_model, field)
        old_value = getattr(old_model, field)
        
        # Check if the values are different
        if new_value != old_value:
            if isinstance(new_value, BaseModel) and isinstance(old_value, BaseModel):
                # If the value is a nested model, recurse
                mutations.extend(
                    get_mutations(old_value, new_value, path + [field])
                )
            else:
                # Add the mutation for primitive types
                mutations.append(StateMutation(
                    path=path + [field],
                    old_value=_create_mutation_value(old_value),
                    new_value=_create_mutation_value(new_value)
                ))
    return mutations


if __name__ == '__main__':
    from pprint import pprint
    
    class DoubleNestedModel(BaseModel):
        other_field: str
    
    class NestedModel(BaseModel):
        nested_field: str
        double_nested: Union[DoubleNestedModel, None]
        double_nested2: Union[DoubleNestedModel, None]
    
    class TestModel(BaseModel):
        name: str
        age: int
        color: str
        is_student: bool
        nested: NestedModel
        my_dict: Dict[str, int]
        my_set: Set[int]
        frozen_set: frozenset
    
    old_model = TestModel(name="John",
                            age=25,
                            color="blue",
                            is_student=False,
                            nested=NestedModel(nested_field="old_value", double_nested=DoubleNestedModel(other_field="new_value"), double_nested2=None),
                            my_dict={"key": 10, "key2": 10},
                            my_set={10, 20},
                            frozen_set=frozenset([10, 20]))
    new_model = TestModel(name="James",
                            age=50,
                            color="blue",
                            is_student=True,
                            nested=NestedModel(nested_field="new_value", double_nested=None, double_nested2=DoubleNestedModel(other_field="new_value")),
                            my_dict={"key": 10, "key2": 20},
                            my_set={10, 30},
                            frozen_set=frozenset([10, 30]))
    
    # Get the mutations required to transform old_model into new_model
    mutations = get_mutations(old_model, new_model)
    pprint(mutations)
    
    # Apply each mutation to the old_model
    for mutation in mutations:
        old_model = apply_mutation(old_model, mutation)
    
    # Print the final state of old_model after all mutations
    pprint(old_model)
