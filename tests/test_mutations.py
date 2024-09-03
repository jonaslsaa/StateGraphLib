from typing import List
import unittest
from pydantic import BaseModel
from pprint import pprint

# Assuming the previous code is saved in a module named `mutations`
from ..mutations import apply_mutation, get_mutations, StateMutation, MutationValue

class NestedModel(BaseModel):
    nested_field: str

class TestModel(BaseModel):
    name: str
    age: int
    color: str
    is_student: bool
    nested: NestedModel
    scores: List[int]

class TestGetMutations(unittest.TestCase):
    
    def setUp(self):
        self.old_model = TestModel(
            name="John",
            age=25,
            color="blue",
            is_student=True,
            nested=NestedModel(nested_field="old_value"),
            scores=[85, 90, 95]
        )
        self.new_model = TestModel(
            name="John",
            age=50,
            color="red",
            is_student=False,
            nested=NestedModel(nested_field="new_value"),
            scores=[85, 95, 100]
        )
    
    def test_primitive_mutation_detection(self):
        # Test detection of primitive type mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        expected_paths = [['age'], ['color'], ['is_student'], ['scores']]
        detected_paths = [mutation.path for mutation in mutations if len(mutation.path) == 1]
        
        self.assertEqual(detected_paths, expected_paths)
    
    def test_nested_model_mutation_detection(self):
        # Test detection of nested model mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        expected_path = [['nested', 'nested_field']]
        detected_paths = [mutation.path for mutation in mutations if 'nested' in mutation.path]
        
        self.assertEqual(detected_paths, expected_path)
    
    def test_list_mutation_detection(self):
        # Test detection of list mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        expected_paths = [['scores']]
        detected_paths = [mutation.path for mutation in mutations if 'scores' in mutation.path]
        
        self.assertEqual(detected_paths, expected_paths)

class TestApplyMutations(unittest.TestCase):
    
    def setUp(self):
        self.old_model = TestModel(
            name="John",
            age=25,
            color="blue",
            is_student=True,
            nested=NestedModel(nested_field="old_value"),
            scores=[85, 90, 95]
        )
        self.new_model = TestModel(
            name="John",
            age=50,
            color="red",
            is_student=False,
            nested=NestedModel(nested_field="new_value"),
            scores=[85, 95, 100]
        )
    
    def test_apply_primitive_mutations(self):
        # Test applying primitive type mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        for mutation in mutations:
            self.old_model = apply_mutation(self.old_model, mutation)
        
        self.assertEqual(self.old_model.age, 50)
        self.assertEqual(self.old_model.color, "red")
        self.assertEqual(self.old_model.is_student, False)
    
    def test_apply_nested_model_mutations(self):
        # Test applying nested model mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        for mutation in mutations:
            self.old_model = apply_mutation(self.old_model, mutation)
        
        self.assertEqual(self.old_model.nested.nested_field, "new_value")
    
    def test_apply_list_mutations(self):
        # Test applying list mutations
        mutations = get_mutations(self.old_model, self.new_model)
        
        for mutation in mutations:
            self.old_model = apply_mutation(self.old_model, mutation)
        
        self.assertEqual(self.old_model.scores, [85, 95, 100])
    
    def test_apply_all_mutations(self):
        # Test applying all mutations together
        mutations = get_mutations(self.old_model, self.new_model)
        
        for mutation in mutations:
            print(f"Applying mutation {mutation}")
            self.old_model = apply_mutation(self.old_model, mutation)
        
        self.assertEqual(self.old_model.age, 50)
        self.assertEqual(self.old_model.color, "red")
        self.assertEqual(self.old_model.is_student, False)
        self.assertEqual(self.old_model.nested.nested_field, "new_value")
        self.assertEqual(self.old_model.scores, [85, 95, 100])

if __name__ == '__main__':
    unittest.main()
