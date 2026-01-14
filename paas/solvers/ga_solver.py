import sys
import random
import time
from typing import List, Tuple, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Runnable


class GASolver(Runnable):
    """
    Genetic Algorithm based solver for the Project Assignment and Scheduling (PaaS) problem.
    It optimizes:
    1. Maximal number of tasks scheduled.
    2. Minimal completion time.
    3. Minimal total cost.
    """

    def __init__(
        self,
        initial_population_size: int = 10,
        max_population_size: int = 50,
        max_generation: int = 200,
        stuck_generation_limit: int = 50,
        time_limit: int = 10,
        seed: int = 8,
    ):
        self.initial_population_size = initial_population_size
        self.max_population_size = max_population_size
        self.max_generation = max_generation
        self.stuck_generation_limit = stuck_generation_limit
        self.time_limit = time_limit
        self.seed = seed
        self.find_neighbor_try = 100
        self.change_team_try = 100

    def _calculate_start_time(
        self, ordering: List[Tuple[int, int]], problem: ProblemInstance
    ) -> List[Assignment]:
        """
        Given an ordered list of (task_id, team_id) pairs,
        schedule tasks when their predecessors are completed and the assigned team is available.
        """
        todo = list(ordering)
        scheduled_finishes = {}  # task_id -> finish_time
        assignments = []
        team_available = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        progress = True
        while progress and todo:
            progress = False
            new_todo = []
            for task_id, team_id in todo:
                if task_id in scheduled_finishes:
                    continue

                task = problem.tasks[task_id]

                # Check predecessors
                preds_done = True
                preds_complete_time = 0
                for p in task.predecessors:
                    if p not in scheduled_finishes:
                        preds_done = False
                        break
                    preds_complete_time = max(
                        preds_complete_time, scheduled_finishes[p]
                    )

                if not preds_done:
                    new_todo.append((task_id, team_id))
                    continue

                # Schedule
                start_time = max(team_available[team_id], preds_complete_time)
                assignments.append(Assignment(task_id, team_id, start_time))
                finish_time = start_time + task.duration
                scheduled_finishes[task_id] = finish_time
                team_available[team_id] = finish_time
                progress = True
            todo = new_todo
        return assignments

    def _evaluate(
        self, assignments: List[Assignment], problem: ProblemInstance
    ) -> Tuple[int, int, int]:
        """
        Returns: (task_count, completion_time, cost)
        """
        if not assignments:
            return 0, sys.maxsize, sys.maxsize

        task_count = len(assignments)
        completion_time = 0
        total_cost = 0

        for a in assignments:
            task = problem.tasks[a.task_id]
            completion_time = max(completion_time, a.start_time + task.duration)
            total_cost += task.compatible_teams.get(a.team_id, 10**12)

        return task_count, completion_time, total_cost

    def _generate_random_individual(
        self, problem: ProblemInstance, tasks_with_teams: List[int]
    ) -> List[Assignment]:
        shuffled_tasks = list(tasks_with_teams)
        random.shuffle(shuffled_tasks)
        ordering = []
        for tid in shuffled_tasks:
            task = problem.tasks[tid]
            team_id = random.choice(list(task.compatible_teams.keys()))
            ordering.append((tid, team_id))
        return self._calculate_start_time(ordering, problem)

    def _crossover(
        self,
        parent1: List[Assignment],
        parent2: List[Assignment],
        problem: ProblemInstance,
    ) -> Tuple[List[Assignment], List[Assignment]]:
        p1_order = [(a.task_id, a.team_id) for a in parent1]
        p2_order = [(a.task_id, a.team_id) for a in parent2]

        def make_child_order(
            a: List[Tuple[int, int]], b: List[Tuple[int, int]]
        ) -> List[Tuple[int, int]]:
            half = len(a) // 2
            chosen = []
            chosen_tasks = set()
            for pair in a[:half]:
                if pair[0] not in chosen_tasks:
                    chosen.append(pair)
                    chosen_tasks.add(pair[0])
            for pair in b:
                if pair[0] not in chosen_tasks:
                    chosen.append(pair)
                    chosen_tasks.add(pair[0])
            return chosen

        c1_order = make_child_order(p1_order, p2_order)
        c2_order = make_child_order(p2_order, p1_order)

        return (
            self._calculate_start_time(c1_order, problem),
            self._calculate_start_time(c2_order, problem),
        )

    def _mutate(
        self, parent: List[Assignment], problem: ProblemInstance
    ) -> Optional[List[Assignment]]:
        orig_order = [(a.task_id, a.team_id) for a in parent]
        if not orig_order:
            return None

        for _ in range(self.find_neighbor_try):
            order = list(orig_order)
            # Swap
            if len(order) >= 2:
                i, j = random.sample(range(len(order)), 2)
                order[i], order[j] = order[j], order[i]

            # Change team
            for __ in range(self.change_team_try):
                idx = random.randrange(len(order))
                task_id, old_team_id = order[idx]
                task = problem.tasks[task_id]
                possible_teams = list(task.compatible_teams.keys())
                if len(possible_teams) <= 1:
                    continue
                other_teams = [tid for tid in possible_teams if tid != old_team_id]
                if not other_teams:
                    continue
                new_team_id = random.choice(other_teams)
                order[idx] = (task_id, new_team_id)
                break

            new_assignments = self._calculate_start_time(order, problem)
            if new_assignments:
                return new_assignments
        return None

    def run(self, problem: ProblemInstance) -> Schedule:
        random.seed(self.seed)
        start_time_ga = time.time()

        tasks_with_teams = [
            tid for tid, task in problem.tasks.items() if task.compatible_teams
        ]
        if not tasks_with_teams:
            return Schedule(assignments=[])

        best_assignments = self._generate_random_individual(problem, tasks_with_teams)
        population = [best_assignments]

        # Initialize population
        for _ in range(self.initial_population_size - 1):
            if time.time() - start_time_ga > self.time_limit:
                break
            population.append(
                self._generate_random_individual(problem, tasks_with_teams)
            )

        stuck_generation = 0
        generation = 0

        while generation < self.max_generation and (
            time.time() - start_time_ga < self.time_limit
        ):
            population = [p for p in population if p]
            if not population:
                break

            # Evaluate and sort
            population.sort(
                key=lambda x: self._evaluate(x, problem),
                reverse=False,  # We want to maximize count, minimize time, minimize cost
            )
            # wait, _evaluate returns (count, time, cost).
            # To sort correctly: count DESC, time ASC, cost ASC.
            # Python's sort is ascending. So we use a key that negates count.
            population.sort(
                key=lambda x: (
                    -self._evaluate(x, problem)[0],
                    self._evaluate(x, problem)[1],
                    self._evaluate(x, problem)[2],
                )
            )

            num_best = max(len(population) // 2, 2)
            best_population = population[:num_best]

            new_pop = list(population)

            # Crossover
            for _ in range(num_best):
                if time.time() - start_time_ga > self.time_limit:
                    break
                if len(best_population) < 2:
                    break
                p1, p2 = random.sample(best_population, 2)
                c1, c2 = self._crossover(p1, p2, problem)
                if c1:
                    new_pop.append(c1)
                if c2:
                    new_pop.append(c2)

            # Mutation
            for _ in range(num_best):
                if time.time() - start_time_ga > self.time_limit:
                    break
                p = random.choice(best_population)
                mchild = self._mutate(p, problem)
                if mchild:
                    new_pop.append(mchild)

            population = new_pop

            # Update best
            prev_best_eval = self._evaluate(best_assignments, problem)

            # Combine current population and previous best to find the new best
            all_candidates = population + [best_assignments]
            all_candidates = [p for p in all_candidates if p]
            all_candidates.sort(
                key=lambda x: (
                    -self._evaluate(x, problem)[0],
                    self._evaluate(x, problem)[1],
                    self._evaluate(x, problem)[2],
                )
            )

            if all_candidates:
                best_assignments = all_candidates[0]

            current_best_eval = self._evaluate(best_assignments, problem)

            if current_best_eval == prev_best_eval:
                stuck_generation += 1
            else:
                stuck_generation = 0

            if stuck_generation >= self.stuck_generation_limit:
                break

            # Trim population
            if len(population) > self.max_population_size:
                population = random.sample(population, self.initial_population_size)

            generation += 1

        return Schedule(assignments=best_assignments)
