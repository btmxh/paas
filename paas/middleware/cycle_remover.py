import sys
from typing import Set, List, Dict

from paas.middleware.base import MapProblem
from paas.models import ProblemInstance, Task


class CycleRemover(MapProblem):
    """
    Middleware that removes tasks involved in dependency cycles
    and any tasks that depend on them (transitively).
    """

    def map_problem(self, problem: ProblemInstance) -> ProblemInstance:
        tasks = problem.tasks

        # 1. Identify tasks involved in cycles (SCCs)
        sccs = self._find_sccs(tasks)

        cycle_tasks = set()
        for scc in sccs:
            if len(scc) > 1:
                cycle_tasks.update(scc)
            elif len(scc) == 1:
                node = scc[0]
                # Check for self-loop
                if node in tasks[node].successors:
                    cycle_tasks.update(scc)

        if not cycle_tasks:
            return problem

        # 2. Create new problem instance (removing only cycle tasks)
        new_tasks: Dict[int, Task] = {}

        for task_id, task in tasks.items():
            if task_id in cycle_tasks:
                continue

            # We DO NOT clean up predecessors or successors here.
            # We leave the dangling references for the DependencyPruner to handle.
            # This ensures that dependent tasks (which now have missing predecessors)
            # will be correctly identified and removed by the Pruner.

            new_task = Task(
                id=task.id,
                duration=task.duration,
                predecessors=list(task.predecessors),  # Shallow copy
                successors=list(task.successors),  # Shallow copy
                compatible_teams=task.compatible_teams.copy(),
            )
            new_tasks[task_id] = new_task

        print(f"CycleRemover: Removed {len(cycle_tasks)} tasks (involved in cycles).")

        return ProblemInstance(
            num_tasks=len(new_tasks),
            num_teams=problem.num_teams,
            tasks=new_tasks,
            teams=problem.teams,
        )

    def _find_sccs(self, tasks: Dict[int, Task]) -> List[List[int]]:
        """
        Tarjan's algorithm to find SCCs.
        """
        visited: Set[int] = set()
        stack: List[int] = []
        on_stack: Set[int] = set()
        ids: Dict[int, int] = {}
        low: Dict[int, int] = {}

        sccs: List[List[int]] = []
        id_counter = [0]

        # Increase recursion limit just in case, though iterative would be better for huge graphs.
        # Capturing current limit to restore? No, just setting it high enough is common in CP.
        sys.setrecursionlimit(max(sys.getrecursionlimit(), len(tasks) + 1000))

        def dfs(at: int):
            stack.append(at)
            on_stack.add(at)
            visited.add(at)
            ids[at] = id_counter[0]
            low[at] = id_counter[0]
            id_counter[0] += 1

            for to in tasks[at].successors:
                # 'to' might not exist in tasks if input is malformed, but assuming valid graph structure within tasks keys
                if to not in tasks:
                    continue

                if to not in visited:
                    dfs(to)
                    low[at] = min(low[at], low[to])
                elif to in on_stack:
                    low[at] = min(low[at], ids[to])

            if ids[at] == low[at]:
                current_scc = []
                while stack:
                    node = stack.pop()
                    on_stack.remove(node)
                    current_scc.append(node)
                    if node == at:
                        break
                sccs.append(current_scc)

        for task_id in tasks:
            if task_id not in visited:
                dfs(task_id)

        return sccs
