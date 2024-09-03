from typing import List, Dict, Set, Union
import unittest
from pydantic import BaseModel
from ..mutations import apply_mutation, get_mutations, StateMutation, MutationValue, create_mutation_value, validate_mutation

class NestedModel(BaseModel):
    nested_field: str

class ComplexModel(BaseModel):
    name: str
    age: int
    color: str
    is_student: bool
    nested: NestedModel
    scores: List[int]
    tags: Set[str]
    metadata: Dict[str, Union[int, str]]

class TestGetMutations(unittest.TestCase):
    
    def setUp(self):
        self.old_model = ComplexModel(
            name="John",
            age=25,
            color="blue",
            is_student=True,
            nested=NestedModel(nested_field="old_value"),
            scores=[85, 90, 95],
            tags={"student", "undergraduate"},
            metadata={"year": 2023, "department": "Computer Science"}
        )
        self.new_model = ComplexModel(
            name="John",
            age=26,
            color="red",
            is_student=False,
            nested=NestedModel(nested_field="new_value"),
            scores=[85, 95, 100],
            tags={"graduate", "research"},
            metadata={"year": 2024, "department": "Data Science", "advisor": "Dr. Smith"}
        )
    
    def test_primitive_mutation_detection(self):
        mutations = get_mutations(self.old_model, self.new_model)
        expected_paths = [['age'], ['color'], ['is_student']]
        detected_paths = [mutation.path for mutation in mutations if len(mutation.path) == 1 and mutation.path[0] in ['age', 'color', 'is_student']]
        self.assertEqual(sorted(detected_paths), sorted(expected_paths))
    
    def test_nested_model_mutation_detection(self):
        mutations = get_mutations(self.old_model, self.new_model)
        expected_path = [['nested', 'nested_field']]
        detected_paths = [mutation.path for mutation in mutations if 'nested' in mutation.path]
        self.assertEqual(detected_paths, expected_path)
    
    def test_list_mutation_detection(self):
        mutations = get_mutations(self.old_model, self.new_model)
        expected_paths = [['scores']]
        detected_paths = [mutation.path for mutation in mutations if 'scores' in mutation.path]
        self.assertEqual(detected_paths, expected_paths)
    
    def test_set_mutation_detection(self):
        mutations = get_mutations(self.old_model, self.new_model)
        expected_paths = [['tags']]
        detected_paths = [mutation.path for mutation in mutations if 'tags' in mutation.path]
        self.assertEqual(detected_paths, expected_paths)
    
    def test_dict_mutation_detection(self):
        mutations = get_mutations(self.old_model, self.new_model)
        expected_paths = [['metadata']]
        detected_paths = [mutation.path for mutation in mutations if 'metadata' in mutation.path]
        self.assertEqual(detected_paths, expected_paths)

class TestApplyMutations(unittest.TestCase):
    
    def setUp(self):
        self.model = ComplexModel(
            name="John",
            age=25,
            color="blue",
            is_student=True,
            nested=NestedModel(nested_field="old_value"),
            scores=[85, 90, 95],
            tags={"student", "undergraduate"},
            metadata={"year": 2023, "department": "Computer Science"}
        )
    
    def test_apply_primitive_mutations(self):
        mutations = [
            StateMutation(path=['age'], old_value=create_mutation_value(25), new_value=create_mutation_value(26)),
            StateMutation(path=['color'], old_value=create_mutation_value("blue"), new_value=create_mutation_value("red")),
            StateMutation(path=['is_student'], old_value=create_mutation_value(True), new_value=create_mutation_value(False))
        ]
        for mutation in mutations:
            self.model = apply_mutation(self.model, mutation)
        
        self.assertEqual(self.model.age, 26)
        self.assertEqual(self.model.color, "red")
        self.assertEqual(self.model.is_student, False)
    
    def test_apply_nested_model_mutations(self):
        mutation = StateMutation(
            path=['nested', 'nested_field'],
            old_value=create_mutation_value("old_value"),
            new_value=create_mutation_value("new_value")
        )
        self.model = apply_mutation(self.model, mutation)
        self.assertEqual(self.model.nested.nested_field, "new_value")
    
    def test_apply_list_mutations(self):
        mutation = StateMutation(
            path=['scores'],
            old_value=create_mutation_value([85, 90, 95]),
            new_value=create_mutation_value([85, 95, 100])
        )
        self.model = apply_mutation(self.model, mutation)
        self.assertEqual(self.model.scores, [85, 95, 100])
    
    def test_apply_set_mutations(self):
        mutation = StateMutation(
            path=['tags'],
            old_value=create_mutation_value({"student", "undergraduate"}),
            new_value=create_mutation_value({"graduate", "research"})
        )
        self.model = apply_mutation(self.model, mutation)
        self.assertEqual(self.model.tags, {"graduate", "research"})
    
    def test_apply_dict_mutations(self):
        mutation = StateMutation(
            path=['metadata'],
            old_value=create_mutation_value({"year": 2023, "department": "Computer Science"}),
            new_value=create_mutation_value({"year": 2024, "department": "Data Science", "advisor": "Dr. Smith"})
        )
        self.model = apply_mutation(self.model, mutation)
        self.assertEqual(self.model.metadata, {"year": 2024, "department": "Data Science", "advisor": "Dr. Smith"})

class TestValidateMutation(unittest.TestCase):
    
    def setUp(self):
        self.model = ComplexModel(
            name="John",
            age=25,
            color="blue",
            is_student=True,
            nested=NestedModel(nested_field="old_value"),
            scores=[85, 90, 95],
            tags={"student", "undergraduate"},
            metadata={"year": 2023, "department": "Computer Science"}
        )
    
    def test_valid_mutation(self):
        mutation = StateMutation(
            path=['age'],
            old_value=create_mutation_value(25),
            new_value=create_mutation_value(26)
        )
        self.assertTrue(validate_mutation(self.model, mutation))
    
    def test_invalid_path(self):
        mutation = StateMutation(
            path=['invalid_field'],
            old_value=create_mutation_value("old"),
            new_value=create_mutation_value("new")
        )
        self.assertFalse(validate_mutation(self.model, mutation))
    
    def test_invalid_old_value(self):
        mutation = StateMutation(
            path=['age'],
            old_value=create_mutation_value(30),  # Incorrect old value
            new_value=create_mutation_value(26)
        )
        self.assertFalse(validate_mutation(self.model, mutation, ignore_old_value=False))
    
    def test_invalid_new_value_type(self):
        mutation = StateMutation(
            path=['age'],
            old_value=create_mutation_value(25),
            new_value=create_mutation_value("twenty-six")  # Invalid type for age
        )
        self.assertFalse(validate_mutation(self.model, mutation))

if __name__ == '__main__':
    unittest.main()
