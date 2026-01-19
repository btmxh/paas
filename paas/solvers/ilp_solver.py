from ortools.linear_solver import pywraplp

from paas.middleware.base import Runnable
from paas.models import ProblemInstance, Schedule, Assignment


class ILPSolver(Runnable):
    """
    ILP Solver using OR-Tools (SAT backend via linear solver interface).
    Performs 3-stage optimization:
    1. Maximize assigned tasks
    2. Minimize makespan (completion time)
    3. Minimize total cost
    """

    def run(self, problem: ProblemInstance) -> Schedule:
        # Mapping
        task_ids = list(problem.tasks.keys())
        task_id_to_idx = {t_id: i for i, t_id in enumerate(task_ids)}

        # Data preparation
        num_tasks = len(task_ids)
        team_ids = list(problem.teams.keys())
        team_id_to_idx = {t_id: i for i, t_id in enumerate(team_ids)}

        durations = [problem.tasks[t_id].duration for t_id in task_ids]
        start_team_time = [problem.teams[t_id].available_from for t_id in team_ids]

        # Constraints (edges)
        constraints = []
        for t_id in task_ids:
            u = task_id_to_idx[t_id]
            for succ_id in problem.tasks[t_id].successors:
                if succ_id in task_id_to_idx:
                    v = task_id_to_idx[succ_id]
                    constraints.append((u, v))

        # Costs
        costs = {}
        for t_id in task_ids:
            u = task_id_to_idx[t_id]
            for team_id, cost in problem.tasks[t_id].compatible_teams.items():
                if team_id in team_id_to_idx:
                    v = team_id_to_idx[team_id]
                    costs[(u, v)] = cost

        remain_tasks = list(range(num_tasks))

        MAX_INT = int(1e9)
        num_teams_count = len(team_ids)

        # --- Phase 1: Maximize assigned tasks ---
        solver = pywraplp.Solver.CreateSolver("SAT")
        if not solver:
            # Fallback if SAT not available, though user script used SAT
            # SCIP or CBC might be available
            solver = pywraplp.Solver.CreateSolver("SCIP")
            if not solver:
                raise RuntimeError("No suitable solver backend found")

        assigned_tasks = {}
        task2team = {}
        start_task_time = {}

        comp_time = solver.IntVar(0, solver.infinity(), "max_time")

        for task in remain_tasks:
            assigned_tasks[task] = solver.IntVar(0, 1, f"task{task}")
            start_task_time[task] = solver.IntVar(0, solver.infinity(), f"start{task}")

            for team in range(num_teams_count):
                if (task, team) in costs:
                    task2team[(task, team)] = solver.IntVar(0, 1, f"t2t{(task, team)}")

        # constraints
        for task in remain_tasks:
            # assigned_tasks[task] == sum(task2team...)
            solver.Add(
                assigned_tasks[task]
                == sum(
                    task2team[(task, team)]
                    for team in range(num_teams_count)
                    if (task, team) in costs
                )
            )
            solver.Add(assigned_tasks[task] <= 1)
            solver.Add(start_task_time[task] + durations[task] <= comp_time)

            for team in range(num_teams_count):
                if (task, team) in costs:
                    solver.Add(
                        start_task_time[task]
                        >= start_team_time[team] * task2team[(task, team)]
                    )

        for task_i, task_j in constraints:
            if task_i in remain_tasks and task_j in remain_tasks:
                solver.Add(
                    start_task_time[task_j]
                    + MAX_INT * (2 - assigned_tasks[task_i] - assigned_tasks[task_j])
                    >= start_task_time[task_i] + durations[task_i]
                )

        solver.Maximize(sum(assigned_tasks[task] for task in remain_tasks))
        status = solver.Solve()

        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return Schedule(assignments=[])

        max_tasks = int(solver.Objective().Value())

        # --- Phase 2: Minimize completion time ---
        solver = pywraplp.Solver.CreateSolver("SAT")
        # Reuse or recreate? Recreate to be clean
        if not solver:
            solver = pywraplp.Solver.CreateSolver("SCIP")

        assigned_tasks = {}
        task2team = {}
        start_task_time = {}
        comp_time = solver.IntVar(0, solver.infinity(), "max_time")

        for task in remain_tasks:
            assigned_tasks[task] = solver.IntVar(0, 1, f"task{task}")
            start_task_time[task] = solver.IntVar(0, solver.infinity(), f"start{task}")

            for team in range(num_teams_count):
                if (task, team) in costs:
                    task2team[(task, team)] = solver.IntVar(0, 1, f"t2t{(task, team)}")

        for task in remain_tasks:
            solver.Add(
                assigned_tasks[task]
                == sum(
                    task2team[(task, team)]
                    for team in range(num_teams_count)
                    if (task, team) in costs
                )
            )
            solver.Add(assigned_tasks[task] <= 1)
            solver.Add(start_task_time[task] + durations[task] <= comp_time)

            for team in range(num_teams_count):
                if (task, team) in costs:
                    solver.Add(
                        start_task_time[task]
                        >= start_team_time[team] * task2team[(task, team)]
                    )

        for task_i, task_j in constraints:
            if task_i in remain_tasks and task_j in remain_tasks:
                solver.Add(
                    start_task_time[task_j]
                    + MAX_INT * (2 - assigned_tasks[task_i] - assigned_tasks[task_j])
                    >= start_task_time[task_i] + durations[task_i]
                )

        solver.Add(sum(assigned_tasks[task] for task in remain_tasks) >= max_tasks)

        solver.Minimize(comp_time)
        status = solver.Solve()

        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return Schedule(assignments=[])

        min_complete_time = int(comp_time.solution_value())

        # --- Phase 3: Minimize cost ---
        solver = pywraplp.Solver.CreateSolver("SAT")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("SCIP")

        assigned_tasks = {}
        task2team = {}
        start_task_time = {}

        for task in remain_tasks:
            assigned_tasks[task] = solver.IntVar(0, 1, f"task{task}")
            start_task_time[task] = solver.IntVar(0, solver.infinity(), f"start{task}")

            for team in range(num_teams_count):
                if (task, team) in costs:
                    task2team[(task, team)] = solver.IntVar(0, 1, f"t2t{(task, team)}")

        for task in remain_tasks:
            solver.Add(
                assigned_tasks[task]
                == sum(
                    task2team[(task, team)]
                    for team in range(num_teams_count)
                    if (task, team) in costs
                )
            )
            solver.Add(assigned_tasks[task] <= 1)
            solver.Add(start_task_time[task] + durations[task] <= min_complete_time)

            for team in range(num_teams_count):
                if (task, team) in costs:
                    solver.Add(
                        start_task_time[task]
                        >= start_team_time[team] * task2team[(task, team)]
                    )

        for task_i, task_j in constraints:
            if task_i in remain_tasks and task_j in remain_tasks:
                solver.Add(
                    start_task_time[task_j]
                    + MAX_INT * (2 - assigned_tasks[task_i] - assigned_tasks[task_j])
                    >= start_task_time[task_i] + durations[task_i]
                )

        solver.Add(sum(assigned_tasks[task] for task in remain_tasks) >= max_tasks)

        solver.Minimize(
            sum(
                costs[(task, team)] * task2team[(task, team)]
                for task in remain_tasks
                for team in range(num_teams_count)
                if (task, team) in costs
            )
        )

        status = solver.Solve()

        result_assignments = []
        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            for task in remain_tasks:
                for team in range(num_teams_count):
                    if (task, team) in costs:
                        if int(task2team[(task, team)].solution_value()) == 1:
                            original_task_id = task_ids[task]
                            original_team_id = team_ids[team]
                            start = int(start_task_time[task].solution_value())

                            result_assignments.append(
                                Assignment(
                                    task_id=original_task_id,
                                    team_id=original_team_id,
                                    start_time=start,
                                )
                            )

        return Schedule(assignments=result_assignments)
