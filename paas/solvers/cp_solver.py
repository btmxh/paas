from typing import List
from ortools.sat.python import cp_model
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver
from paas.time_budget import TimeBudget


class CPSolver(Solver):
    """
    CP-SAT solver for the Project Assignment and Scheduling problem.
    """

    def __init__(self, time_factor: float = 1.0):
        super().__init__(time_factor)

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        if not problem.tasks:
            return Schedule(assignments=[])

        with TimeBudget(time_limit) as budget:
            # Heuristic for the maximum possible time
            max_duration = sum(t.duration for t in problem.tasks.values())
            max_start = max(
                (t.available_from for t in problem.teams.values()), default=0
            )
            horizon = max_duration + max_start + 1000

            # Lexicographical optimization:
            # 1. Minimize completion time
            min_makespan = self._solve_min_makespan(problem, horizon, budget)

            # 2. Minimize total cost
            assignments = self._solve_min_cost(problem, horizon, min_makespan, budget)

            return Schedule(assignments=assignments)

    def _create_base_model(self, problem: ProblemInstance, horizon: int):
        model = cp_model.CpModel()

        start_times = {}  # task_id -> int var
        end_times = {}  # task_id -> int var
        presence = {}  # (task_id, team_id) -> bool var
        intervals = {
            team_id: [] for team_id in problem.teams
        }  # team_id -> list of interval vars

        # Initialize variables for all tasks first
        for task_id, task in problem.tasks.items():
            start_times[task_id] = model.NewIntVar(0, horizon, f"start_{task_id}")
            end_times[task_id] = model.NewIntVar(0, horizon, f"end_{task_id}")
            model.Add(end_times[task_id] == start_times[task_id] + task.duration)

        for task_id, task in problem.tasks.items():
            # Team assignments
            task_team_vars = []
            for team_id, cost in task.compatible_teams.items():
                if team_id not in problem.teams:
                    continue
                p_var = model.NewBoolVar(f"presence_{task_id}_{team_id}")
                presence[(task_id, team_id)] = p_var
                task_team_vars.append(p_var)

                # Interval for NoOverlap
                interval = model.NewOptionalIntervalVar(
                    start_times[task_id],
                    task.duration,
                    end_times[task_id],
                    p_var,
                    f"interval_{task_id}_{team_id}",
                )
                intervals[team_id].append(interval)

                # Team availability
                model.Add(
                    start_times[task_id] >= problem.teams[team_id].available_from
                ).OnlyEnforceIf(p_var)

            model.Add(sum(task_team_vars) == 1)

            # Precedence constraints
            for pred_id in task.predecessors:
                if pred_id in problem.tasks:
                    # precedence
                    model.Add(start_times[task_id] >= end_times[pred_id])

        # Team NoOverlap
        for team_id, team_intervals in intervals.items():
            if team_intervals:
                model.AddNoOverlap(team_intervals)

        return model, start_times, presence, end_times

    def _solve_min_makespan(
        self, problem: ProblemInstance, horizon: int, budget: TimeBudget
    ) -> int:
        model, start_times, presence, end_times = self._create_base_model(
            problem, horizon
        )

        # Define makespan
        makespan = model.NewIntVar(0, horizon, "makespan")
        for task_id in problem.tasks:
            model.Add(makespan >= end_times[task_id])

        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        if budget.remaining() < float("inf"):
            solver.parameters.max_time_in_seconds = budget.remaining()

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return int(solver.Value(makespan))
        return horizon

    def _solve_min_cost(
        self,
        problem: ProblemInstance,
        horizon: int,
        min_makespan: int,
        budget: TimeBudget,
    ) -> List[Assignment]:
        model, start_times, presence, end_times = self._create_base_model(
            problem, horizon
        )

        for task_id in problem.tasks:
            model.Add(end_times[task_id] <= min_makespan)

        # Objective: minimize cost
        total_cost = []
        for (task_id, team_id), p_var in presence.items():
            cost = problem.tasks[task_id].compatible_teams[team_id]
            total_cost.append(p_var * cost)

        model.Minimize(sum(total_cost))

        solver = cp_model.CpSolver()
        if budget.remaining() < float("inf"):
            solver.parameters.max_time_in_seconds = budget.remaining()

        status = solver.Solve(model)

        assignments = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for task_id in problem.tasks:
                # Find which team
                assigned_team = -1
                for team_id in problem.tasks[task_id].compatible_teams:
                    if solver.Value(presence[(task_id, team_id)]):
                        assigned_team = team_id
                        break

                assignments.append(
                    Assignment(
                        task_id=task_id,
                        team_id=assigned_team,
                        start_time=solver.Value(start_times[task_id]),
                    )
                )
        return assignments
