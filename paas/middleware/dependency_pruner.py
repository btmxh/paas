from paas.middleware.base import MapProblem
from paas.models import ProblemInstance, Task


class DependencyPruner(MapProblem):
    """
    Middleware that removes tasks that depend on missing tasks (transitively),
    and cleans up stale references in adjacency lists.
    """

    def map_problem(self, problem: ProblemInstance) -> ProblemInstance:
        tasks = problem.tasks

        # 1. Identify tasks with missing predecessors
        # We also need to handle the case where a task points to a predecessor that isn't in 'tasks'
        valid_ids = set(tasks.keys())

        to_remove: set[int] = set()
        queue: list[int] = []

        # Find initial broken tasks
        for t_id, task in tasks.items():
            # Check if any predecessor is missing from the valid_ids
            # (e.g. removed by previous middleware)
            if any(p not in valid_ids for p in task.predecessors):
                to_remove.add(t_id)
                queue.append(t_id)

        # 2. Propagate removal to successors
        while queue:
            current_id = queue.pop(0)

            # The task might have been removed from 'tasks' map in a real-time update scenario,
            # but here we are just building a set of IDs to remove.
            # We need to look up its successors.
            # However, if 'current_id' is not in 'tasks' (e.g. it was missing to begin with),
            # we can't look up its successors.
            # But 'current_id' comes from 'tasks.items()', so it exists.
            # Wait, if we propagate:
            # A (removed) -> B. B is added to queue.
            # When we pop B, B is in 'tasks'. So we get its successors.

            if current_id not in tasks:
                # Should not happen for the initial set, but for propagated ones?
                # Propagated ones are found via successors of existing tasks, so they should exist?
                # Unless the graph has a pointer to a non-existent task?
                # If A -> B, and B is not in tasks.
                # A is removed. We check A's successors. B is one.
                # We add B to queue.
                # We pop B. B is not in tasks.
                continue

            current_task = tasks[current_id]
            for succ_id in current_task.successors:
                if succ_id not in to_remove and succ_id in tasks:
                    to_remove.add(succ_id)
                    queue.append(succ_id)

        # 3. Create new task list and clean up references
        new_tasks: dict[int, Task] = {}

        final_valid_ids = valid_ids - to_remove

        for t_id, task in tasks.items():
            if t_id in to_remove:
                continue

            # Clean up successors: remove any that are being removed
            new_successors = [s for s in task.successors if s in final_valid_ids]

            # Clean up predecessors: remove any that are being removed?
            # Ideally, if we did our job right, all predecessors of a kept task
            # MUST be in final_valid_ids.
            # Let's just filter to be safe and consistent.
            new_predecessors = [p for p in task.predecessors if p in final_valid_ids]

            new_task = Task(
                id=task.id,
                duration=task.duration,
                predecessors=new_predecessors,
                successors=new_successors,
                compatible_teams=task.compatible_teams.copy(),
            )
            new_tasks[t_id] = new_task

        if to_remove:
            print(
                f"DependencyPruner: Removed {len(to_remove)} tasks (broken dependencies)."
            )

        return ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams=problem.teams,
        )
