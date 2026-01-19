import unittest
import os
import shutil
import tempfile
from paas.dataset import Dataset


class TestDataset(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.generated_dir = os.path.join(self.test_dir, "data", "generated_dataset")
        os.makedirs(self.generated_dir)

        # Create a dummy instance
        self.instance_content = """2 1
1 2
10 20
2
0 0
2
1 1 10
2 2 20
"""
        with open(os.path.join(self.generated_dir, "test_instance.txt"), "w") as f:
            f.write(self.instance_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generated_dataset_loading(self):
        # We need to monkeypatch Dataset to look at our temp dir instead of relative to cwd
        # Or just change cwd for the test
        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            dataset = Dataset.generated()
            self.assertEqual(len(dataset.instances), 1)
            instance = dataset.instances[0]
            self.assertEqual(instance.id, "test_instance")
            self.assertEqual(instance.problem.num_tasks, 2)
            self.assertEqual(instance.problem.num_teams, 2)
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
