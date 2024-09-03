from typing import Any, List, Dict, Union, Set
from pydantic import BaseModel, create_model
import pydantic
import json

# Requries pydantic >= 2
if pydantic.__version__.startswith('1.') or pydantic.__version__.startswith('0.'):
    print("[WARNING] It seems you are using pydantic <2.0. Please upgrade to the latest version.")

FLAG_UNKNOWN_MODELS_CONVERTED_TO_DICT = False
FLAG_ALLOW_MIXING_BETWEEN_PRIMITIVE_AND_NESTED = False

class MutationValue(BaseModel):
    value: str
    type_name: str  # Supports JSON serializable types (int, str, bool, list, dict) and also Sets, BaseModel is also supported
    value_model_schema: Union[Dict[str, Any], None] = None # Optional schema to validate the new value (must be a Pydantic model)

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

def _deserialize(mutation_value: MutationValue) -> Any:
    '''
    Deserialize a string to a value.
    '''
    if mutation_value.type_name == 'set':
        return set(json.loads(mutation_value.value))
    if mutation_value.type_name == 'frozenset':
        return frozenset(json.loads(mutation_value.value))
    if mutation_value.type_name == 'BaseModel':
        raise NotImplementedError("Deserializing unknown nested models is not supported, and will not be implemented. Turn on the FLAG_UNKNOWN_MODELS_CONVERTED_TO_DICT flag to convert unknown models to dictionaries.")
    return json.loads(mutation_value.value)

def create_mutation_value(value: Any) -> MutationValue:
    '''
    Create a MutationValue object from a value.
    '''
    type_name = type(value).__name__
    
    # Handle nested models
    schema = None
    if isinstance(value, BaseModel):
        # Get classes schema
        schema = value.__class__.model_json_schema(mode='serialization')
        if not FLAG_UNKNOWN_MODELS_CONVERTED_TO_DICT:
            type_name = 'BaseModel'
        
    # Return the MutationValue object
    return MutationValue(
        value=_serialize(value),
        type_name=type_name,
        value_model_schema=schema
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
    setattr(value, mutation.path[-1], _deserialize(mutation.new_value))
    
    return old_value  # Return the modified model

def get_mutations(old_model: BaseModel, new_model: BaseModel, path: List[str] = []):
    '''
    Get the mutations that need to be applied to old_model to get to new_model.
    '''
    mutations: List[StateMutation] = []
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
                if any([isinstance(new_value, BaseModel), isinstance(old_value, BaseModel)]) and not FLAG_ALLOW_MIXING_BETWEEN_PRIMITIVE_AND_NESTED:
                    raise ValueError(f"Mixing between primitive and nested models is not allowed. Field: {field}. Turn on the FLAG_ALLOW_MIXING_BETWEEN_PRIMITIVE_AND_NESTED flag to allow this.")
                # Add the mutation for primitive types
                mutations.append(StateMutation(
                    path =       path + [field],
                    old_value =  create_mutation_value(old_value),
                    new_value =  create_mutation_value(new_value)
                ))
    return mutations

def validate_mutation(old_model: BaseModel, mutation: StateMutation, ignore_old_value=True):
    '''
    Validate a mutation against a model.

    Returns True if the mutation is valid, False otherwise.
    '''
    # Try to apply the mutation
    try:
        # Create a copy of the model to avoid modifying the original
        model_copy = old_model.model_copy(deep=True)
        
        # Traverse to the parent of the attribute to change
        value = model_copy
        for p in mutation.path[:-1]:
            value = getattr(value, p)
        
        # Get the field info
        field = value.model_fields[mutation.path[-1]]
        
        # Validate the new value against the field type
        field.validate(json.loads(mutation.new_value.value), {})
        
        # If we got here, the new value is valid for the field
        # Now try to apply the mutation
        apply_mutation(model_copy, mutation, ignore_old_value=ignore_old_value)
    except (AttributeError, KeyError): # Expected if the path does not exist
        return False
    except ValueError: # Expected if the old value does not match the current value
        return False
    except pydantic.ValidationError: # Expected if the new value is not valid for the field
        return False
    return True


# Example usage
if __name__ == '__main__':
    from pprint import pprint
    
    class DoubleNestedModel(BaseModel):
        other_field: str
    
    class NestedModel(BaseModel):
        nested_field: str
        double_nested: Union[DoubleNestedModel, None]
    
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
                            nested=NestedModel(nested_field="old_value", double_nested=DoubleNestedModel(other_field="abc")),
                            my_dict={"key": 10, "key2": 10},
                            my_set={10, 20},
                            frozen_set=frozenset([10, 20]))
    new_model = TestModel(name="James",
                            age=50,
                            color="blue",
                            is_student=True,
                            nested=NestedModel(nested_field="new_value", double_nested=DoubleNestedModel(other_field="def")),
                            my_dict={"key": 10, "key3": 20},
                            my_set={10, 30},
                            frozen_set=frozenset([10, 30]))
    
    # Get the mutations required to transform old_model into new_model
    mutations = get_mutations(old_model, new_model)
    print("\n * Mutations:")
    pprint(mutations)
    
    # Apply each mutation to the old_model
    for mutation in mutations:
        old_model = apply_mutation(old_model, mutation)
    
    # Print the final state of old_model after all mutations
    print("\n\n * Final state of old_model:")
    pprint(old_model)
    
    
    print("\n\n Testing validation of mutations:")
    # Validate a mutation
    ## Testing valid mutation
    m = StateMutation(
        path=['name'],
        old_value=create_mutation_value('John'),
        new_value=create_mutation_value('James')
    )
    print(validate_mutation(old_model, m))  # Should return True
    
    ## Testing invalid mutation
    m = StateMutation(
        path=['full_name'], # Invalid path
        old_value=create_mutation_value('John'),
        new_value=create_mutation_value('James')
    )
    
    print(validate_mutation(old_model, m))  # Should return False
    
    
