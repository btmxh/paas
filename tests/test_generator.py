import unittest
import io
from paas.generator import generate_instance, serialize_instance
from paas.parser import parse_input


class TestGenerator(unittest.TestCase):
    def test_generate_and_parse(self):
        # Generate an instance
        n_tasks = 20
        n_teams = 5
        instance = generate_instance(n_tasks=n_tasks, n_teams=n_teams, seed=42)

        # Serialize it
        serialized = serialize_instance(instance)

        # Parse it back
        input_stream = io.StringIO(serialized)
        parsed_instance = parse_input(input_stream)

        # Verify
        self.assertEqual(parsed_instance.num_tasks, n_tasks)
        self.assertEqual(parsed_instance.num_teams, n_teams)
        self.assertEqual(len(parsed_instance.tasks), n_tasks)
        self.assertEqual(len(parsed_instance.teams), n_teams)

        for i in range(1, n_tasks + 1):
            self.assertEqual(
                parsed_instance.tasks[i].duration, instance.tasks[i].duration
            )
            self.assertEqual(
                set(parsed_instance.tasks[i].predecessors),
                set(instance.tasks[i].predecessors),
            )
            self.assertEqual(
                parsed_instance.tasks[i].compatible_teams,
                instance.tasks[i].compatible_teams,
            )


if __name__ == "__main__":
    unittest.main()
