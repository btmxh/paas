import sys
import json
import time
import concurrent.futures
from typing import List, Dict, Any, Type

from paas.dataset import Dataset, Instance
from paas.grader import grade_schedule, JuryNormalizer

from paas.middleware.base import Pipeline, Solver
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.dependency_pruner import DependencyPruner

import paas.solvers


def get_available_solvers() -> List[Type[Solver]]:
    solver_classes = []
    # inspect paas.solvers.__all__
    if hasattr(paas.solvers, "__all__"):
        for name in paas.solvers.__all__:
            cls = getattr(paas.solvers, name)
            solver_classes.append(cls)
    return solver_classes


def run_single_experiment(
    instance: Instance, solver_cls: Type[Solver], time_limit: int
) -> Dict[str, Any]:
    solver_name = solver_cls.__name__

    # Setup pipeline
    pipeline = Pipeline(
        middlewares=[
            ImpossibleTaskRemover(),
            CycleRemover(),
            DependencyPruner(),
        ],
        solver=solver_cls(),
    )

    start_time = time.time()
    try:
        schedule = pipeline.run(instance.problem, time_limit=time_limit)
        elapsed = time.time() - start_time

        score = grade_schedule(instance.problem, schedule)

        jury_score = None
        if instance.sample_solution_result:
            jury_score = grade_schedule(
                instance.problem, instance.sample_solution_result
            )

        normalizer = JuryNormalizer()
        normalized_scores = normalizer.normalize(score, instance.problem, jury_score)

        return {
            "instance": instance.id,
            "solver": solver_name,
            "status": "success",
            "time_elapsed": elapsed,
            "score": score.to_dict(),
            "normalized": normalized_scores,
            "assignments_count": len(schedule.assignments),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "instance": instance.id,
            "solver": solver_name,
            "status": "failed",
            "error": str(e),
            "time_elapsed": elapsed,
        }


def main():
    dataset = Dataset.hustack()
    solvers = get_available_solvers()
    results = []

    time_limit = 10  # seconds

    if not solvers:
        print("No solvers found!")
        sys.exit(1)

    # Generate tasks
    tasks = []
    for instance in dataset.instances:
        for solver_cls in solvers:
            tasks.append((instance, solver_cls))

    print(
        f"Running {len(tasks)} experiments on {len(dataset.instances)} instances with {len(solvers)} solvers."
    )
    print(f"Time limit per run: {time_limit}s")

    # Use ProcessPoolExecutor for true parallelism
    # Note: If memory usage is too high, reduce max_workers
    with concurrent.futures.ProcessPoolExecutor() as executor:
        future_to_task = {
            executor.submit(run_single_experiment, instance, solver_cls, time_limit): (
                instance.id,
                solver_cls.__name__,
            )
            for instance, solver_cls in tasks
        }

        for future in concurrent.futures.as_completed(future_to_task):
            inst_id, solv_name = future_to_task[future]
            try:
                data = future.result()
                results.append(data)
                status = data["status"]
                if status == "success":
                    score_str = f"Tasks: {data['assignments_count']}, Cost: {data['score']['total_cost']}"
                    # Add normalized score if available
                    if "relative_cost" in data["normalized"]:
                        score_str += (
                            f", RelCost: {data['normalized']['relative_cost']:.2f}"
                        )
                    print(f"[{inst_id}] {solv_name}: Success ({score_str})")
                else:
                    print(f"[{inst_id}] {solv_name}: Failed ({data.get('error')})")
            except Exception as exc:
                print(f"[{inst_id}] {solv_name} generated an exception: {exc}")

    # Dump results
    output_file = "results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()
