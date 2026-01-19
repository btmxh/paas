import os
import subprocess


def main():
    dataset_dir = "data/generated_dataset"
    os.makedirs(dataset_dir, exist_ok=True)

    # Configuration for different scales
    # (name, tasks, teams, dep_ratio, comp_ratio)
    configs = [
        ("small_1", 10, 3, 0.1, 0.5),
        ("small_2", 15, 4, 0.2, 0.4),
        ("medium_1", 50, 10, 0.05, 0.3),
        ("medium_2", 100, 20, 0.1, 0.2),
        ("large_1", 500, 50, 0.02, 0.1),
        ("large_2", 1000, 100, 0.01, 0.05),
    ]

    for name, tasks, teams, dep, comp in configs:
        output_path = os.path.join(dataset_dir, f"{name}.txt")
        cmd = [
            "python3",
            "scripts/generate_test.py",
            "--tasks",
            str(tasks),
            "--teams",
            str(teams),
            "--dep-ratio",
            str(dep),
            "--comp-ratio",
            str(comp),
            "--output",
            output_path,
            "--seed",
            str(hash(name) % 10000),
        ]

        print(f"Generating {output_path}...")
        # Note: In this environment, we should ideally use the bin/uv wrapper
        # but the user asked for a script. I'll make it use sys.executable
        # if run directly or just assume 'python3' is available in the target environment.
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"Failed to generate {name}: {e}")


if __name__ == "__main__":
    main()
