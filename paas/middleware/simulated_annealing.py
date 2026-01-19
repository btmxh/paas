import math
import random
import sys
from typing import List, Dict, Tuple

from paas.middleware.base import MapResult
from paas.models import ProblemInstance, Schedule, Assignment
from paas.time_budget import TimeBudget


class SimulatedAnnealingRefiner(MapResult):
    """
    Middleware that applies Simulated Annealing to refine a schedule.

    It is 'solver-agnostic': it takes an existing Schedule (from Greedy, GA,
    or any other source), converts it into a mutable state (Task Order + Team Map),
    and optimizes it to minimize:
      1. Number of unscheduled tasks (Primary)
      2. Completion time / Makespan (Secondary)
      3. Team Costs (Tertiary)
    """

    def __init__(
        self,
        initial_temp: float = 1000.0,
        seed: int = 42,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.initial_temp = initial_temp
        self.seed = seed

    def map_result(
        self,
        problem: ProblemInstance,
        result: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        """
        The entry point for the middleware.
        Refines the incoming 'result' schedule using Simulated Annealing.
        """
        # If the schedule is empty and there are tasks to schedule, we should try to schedule them.
        # If the problem itself is empty, return.
        if not problem.tasks:
            return result

        random.seed(self.seed)

        # 1. Lift Schedule -> Internal State (Genotype)
        current_order, current_teams = self._schedule_to_state(problem, result)

        # 2. Initialize Energy
        current_assignments, current_fitness = self._evaluate(
            problem, current_order, current_teams
        )
        current_energy = self._calculate_energy(current_fitness)

        best_order = list(current_order)
        best_teams = dict(current_teams)
        best_energy = current_energy

        temperature = self.initial_temp

        use_time_limit = time_limit != float("inf")

        with TimeBudget.from_seconds(time_limit) as budget:
            while True:
                # Check termination condition
                if use_time_limit:
                    if budget.is_expired():
                        break

                    # Update temperature based on remaining time
                    # Linear cooling schedule: T = T_start * (remaining / total)
                    remaining = budget.remaining()
                    # Ensure remaining is non-negative and <= time_limit
                    ratio = max(0.0, min(1.0, remaining / time_limit))
                    temperature = self.initial_temp * ratio

                # If infinite time, we technically run forever at initial_temp
                # (or until externally killed, though this loop won't check external signals explicitly)

                # 3. Create Neighbor (Mutation)
                neighbor_order, neighbor_teams = self._mutate(
                    problem, current_order, current_teams
                )

                # 4. Evaluate Neighbor
                _, neighbor_fitness = self._evaluate(
                    problem, neighbor_order, neighbor_teams
                )
                neighbor_energy = self._calculate_energy(neighbor_fitness)

                # 5. Acceptance Criteria (Metropolis)
                delta_e = neighbor_energy - current_energy
                accept = False

                if delta_e < 0:
                    # Strictly better
                    accept = True
                elif temperature > 1e-10:
                    # Worse, but accept with probability
                    if random.random() < math.exp(-delta_e / temperature):
                        accept = True

                if accept:
                    current_order = neighbor_order
                    current_teams = neighbor_teams
                    current_energy = neighbor_energy

                    # Keep track of absolute best
                    if current_energy < best_energy:
                        best_order = list(current_order)
                        best_teams = dict(current_teams)
                        best_energy = current_energy

        # 7. Decode best state back to Schedule
        final_assignments, _ = self._evaluate(problem, best_order, best_teams)
        return Schedule(assignments=final_assignments)

    def _schedule_to_state(
        self, problem: ProblemInstance, schedule: Schedule
    ) -> Tuple[List[int], Dict[int, int]]:
        """
        Converts a Schedule object into the internal Order and Team Map.
        It ensures ALL tasks in the problem are included in the state, even if
        they weren't scheduled in the input (so SA can try to fit them in).
        """
        # Sort existing assignments by start time to preserve the "good" order
        sorted_assignments = sorted(schedule.assignments, key=lambda a: a.start_time)

        task_order = [a.task_id for a in sorted_assignments]
        team_assignment = {a.task_id: a.team_id for a in sorted_assignments}

        # Identify missing tasks (unscheduled ones)
        scheduled_ids = set(task_order)
        all_task_ids = set(
            tid for tid, t in problem.tasks.items() if t.compatible_teams
        )
        missing_ids = list(all_task_ids - scheduled_ids)

        # Append missing tasks to the end (randomly shuffled)
        random.shuffle(missing_ids)
        task_order.extend(missing_ids)

        # Assign valid random teams to the missing tasks
        for tid in missing_ids:
            compat = list(problem.tasks[tid].compatible_teams.keys())
            if compat:
                team_assignment[tid] = random.choice(compat)

        return task_order, team_assignment

    def _mutate(
        self, problem: ProblemInstance, order: List[int], teams: Dict[int, int]
    ) -> Tuple[List[int], Dict[int, int]]:
        """
        Generates a neighbor by modifying order OR teams.
        Returns NEW copies of list/dict to avoid side effects.
        """
        new_order = list(order)
        new_teams = dict(teams)

        # 50% chance to swap order, 50% chance to change a team
        if random.random() < 0.5 and len(new_order) >= 2:
            # Swap Mutation
            i, j = random.sample(range(len(new_order)), 2)
            new_order[i], new_order[j] = new_order[j], new_order[i]
        else:
            # Team Mutation
            # Pick a random task that has choices
            tid = random.choice(list(new_teams.keys()))
            compat = list(problem.tasks[tid].compatible_teams.keys())
            if len(compat) > 1:
                # Pick a different team
                current_team = new_teams[tid]
                choices = [t for t in compat if t != current_team]
                if choices:
                    new_teams[tid] = random.choice(choices)

        return new_order, new_teams

    def _calculate_energy(self, fitness: Tuple[int, int, int]) -> float:
        """
        Collapses (-task_count, makespan, cost) into a single scalar.
        Lower is better.
        """
        neg_count, makespan, cost = fitness
        # Hierarchy:
        # 1. Maximize Task Count (Minimize neg_count) - Weight 10^12
        # 2. Minimize Makespan - Weight 10^6
        # 3. Minimize Cost - Weight 1
        return (neg_count * 1e12) + (makespan * 1e6) + cost

    def _evaluate(
        self,
        problem: ProblemInstance,
        task_order: List[int],
        team_assignment: Dict[int, int],
    ) -> Tuple[List[Assignment], Tuple[int, int, int]]:
        """
        Decodes the state into a schedule and calculates fitness.
        Returns (assignments, (neg_count, makespan, cost))
        """
        assignments = self._decode(problem, task_order, team_assignment)

        if not assignments:
            return [], (0, sys.maxsize, sys.maxsize)

        count = len(assignments)
        makespan = 0
        total_cost = 0

        for a in assignments:
            task = problem.tasks[a.task_id]
            finish = a.start_time + task.duration
            makespan = max(makespan, finish)
            total_cost += task.compatible_teams.get(a.team_id, 10**12)

        return assignments, (-count, makespan, total_cost)

    def _decode(
        self,
        problem: ProblemInstance,
        task_order: List[int],
        team_assignment: Dict[int, int],
    ) -> List[Assignment]:
        """
        Serial Schedule Generation Scheme (SGS).
        Greedily schedules tasks in 'task_order' as early as dependencies
        and team availability allow.
        """
        scheduled_finishes: Dict[int, int] = {}
        assignments: List[Assignment] = []

        team_available = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        # We need to iterate multiple times if strict order is invalid,
        # but SGS usually just skips unready tasks and retries them.
        pending = list(task_order)

        while pending:
            progress = False
            next_pending = []

            for task_id in pending:
                # 1. Check Predecessors
                task = problem.tasks[task_id]
                preds_ready = True
                preds_finish_time = 0

                for p in task.predecessors:
                    if p not in scheduled_finishes:
                        preds_ready = False
                        break
                    preds_finish_time = max(preds_finish_time, scheduled_finishes[p])

                if not preds_ready:
                    next_pending.append(task_id)
                    continue

                # 2. Schedule
                team_id = team_assignment[task_id]
                start_time = max(team_available[team_id], preds_finish_time)

                assignments.append(Assignment(task_id, team_id, start_time))

                finish_time = start_time + task.duration
                scheduled_finishes[task_id] = finish_time
                team_available[team_id] = finish_time

                progress = True

            if not progress:
                # Either all remaining tasks are cyclic or impossible
                break

            pending = next_pending

        return assignments
