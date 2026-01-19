import sys
import random
import heapq
from dataclasses import dataclass
from typing import List, Tuple, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import MapResult
from paas.time_budget import TimeBudget


@dataclass
class Individual:
    task_order: List[int]
    team_assignment: List[int]
    fitness: Optional[Tuple[int, int, int]] = None


class GAMiddleware(MapResult):
    """
    Genetic Algorithm middleware.
    Takes a schedule (likely from a greedy solver) as an initial seed for the population.
    """

    def __init__(
        self,
        initial_population_size: int = 50,
        max_population_size: int = 200,
        max_generation: int = 100,
        seed: int = 8,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.initial_population_size = initial_population_size
        self.max_population_size = max_population_size
        self.max_generation = max_generation
        self.seed = seed

        # Preprocessed data
        self.num_tasks: int = 0
        self.num_teams: int = 0
        self.durations: List[int] = []
        self.predecessors: List[List[int]] = []
        self.successors: List[List[int]] = []
        self.initial_in_degrees: List[int] = []
        self.compatible_teams_indices: List[List[int]] = []
        self.team_costs: List[List[int]] = []
        self.team_initial_availability: List[int] = []
        self.team_idx_to_id: List[int] = []
        self.tasks_with_teams: List[int] = []

    def _preprocess(self, problem: ProblemInstance):
        problem.assert_continuous_indices()
        self.num_tasks = problem.num_tasks
        self.num_teams = problem.num_teams

        self.team_initial_availability = [0] * self.num_teams
        for tid, team in problem.teams.items():
            self.team_initial_availability[tid] = team.available_from

        self.team_idx_to_id = list(range(self.num_teams))

        self.durations = [0] * self.num_tasks
        self.predecessors = [[] for _ in range(self.num_tasks)]
        self.successors = [[] for _ in range(self.num_tasks)]
        self.initial_in_degrees = [0] * self.num_tasks
        self.compatible_teams_indices = [[] for _ in range(self.num_tasks)]

        INF = 10**12
        self.team_costs = [[INF] * self.num_teams for _ in range(self.num_tasks)]
        self.tasks_with_teams = []

        for tid, task in problem.tasks.items():
            self.durations[tid] = task.duration
            self.predecessors[tid] = task.predecessors
            self.successors[tid] = task.successors
            self.initial_in_degrees[tid] = len(task.predecessors)

            if task.compatible_teams:
                self.tasks_with_teams.append(tid)

            for team_idx, cost in task.compatible_teams.items():
                self.compatible_teams_indices[tid].append(team_idx)
                self.team_costs[tid][team_idx] = cost

    def _schedule_to_individual(self, schedule: Schedule) -> Individual:
        """
        Convert a Schedule object back into an Individual.
        """
        # team_assignment: size N, index=task_id, value=team_idx
        team_assignment = [0] * self.num_tasks

        # We need to reconstruct the team assignments.
        # schedule.assignments uses team_id (which might be 0..M-1 if using ContinuousIndexer)
        # But if it's not, we have a problem.
        # We assume ContinuousIndexer was used, so team_ids are 0..M-1.

        # Also need task_order.
        # We can sort assignments by start_time to get a valid order.
        sorted_assignments = sorted(schedule.assignments, key=lambda a: a.start_time)

        task_order = [a.task_id for a in sorted_assignments]

        # Add unscheduled tasks to the end (randomly or in order)
        scheduled_ids = set(task_order)
        remaining = [tid for tid in self.tasks_with_teams if tid not in scheduled_ids]
        random.shuffle(remaining)
        task_order.extend(remaining)

        for a in schedule.assignments:
            # Assumes a.team_id matches the index logic.
            # If ContinuousIndexer is used, team keys are integers 0..M-1.
            # self._preprocess relies on that.
            team_assignment[a.task_id] = a.team_id

        # Fill assignments for remaining tasks
        for tid in remaining:
            opts = self.compatible_teams_indices[tid]
            if opts:
                team_assignment[tid] = random.choice(opts)

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _decode(self, individual: Individual) -> List[Assignment]:
        priority = [0] * self.num_tasks
        for rank, tid in enumerate(individual.task_order):
            priority[tid] = rank

        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        current_in_degrees = list(self.initial_in_degrees)

        assignments: List[Assignment] = []
        ready_heap = []
        for tid in self.tasks_with_teams:
            if current_in_degrees[tid] == 0:
                heapq.heappush(ready_heap, (priority[tid], tid))

        while ready_heap:
            _, task_id = heapq.heappop(ready_heap)
            team_idx = individual.team_assignment[task_id]

            preds_complete_time = 0
            for p in self.predecessors[task_id]:
                p_finish = task_finish_times[p]
                if p_finish > preds_complete_time:
                    preds_complete_time = p_finish

            start_time = max(team_available[team_idx], preds_complete_time)
            duration = self.durations[task_id]
            finish_time = start_time + duration

            task_finish_times[task_id] = finish_time
            team_available[team_idx] = finish_time

            assignments.append(Assignment(task_id, team_idx, start_time))

            for s in self.successors[task_id]:
                current_in_degrees[s] -= 1
                if current_in_degrees[s] == 0:
                    if self.compatible_teams_indices[s]:
                        heapq.heappush(ready_heap, (priority[s], s))

        return assignments

    def _evaluate(self, individual: Individual) -> Tuple[int, int, int]:
        if individual.fitness is not None:
            return individual.fitness

        assignments = self._decode(individual)

        if not assignments:
            return (0, sys.maxsize, sys.maxsize)

        task_count = len(assignments)
        completion_time = 0
        total_cost = 0

        for a in assignments:
            duration = self.durations[a.task_id]
            finish = a.start_time + duration
            if finish > completion_time:
                completion_time = finish

            cost = self.team_costs[a.task_id][a.team_id]
            total_cost += cost

        individual.fitness = (-task_count, completion_time, total_cost)
        return individual.fitness

    def _generate_random_individual(self) -> Individual:
        task_order = list(self.tasks_with_teams)
        random.shuffle(task_order)
        team_assignment = [0] * self.num_tasks
        for tid in self.tasks_with_teams:
            opts = self.compatible_teams_indices[tid]
            if opts:
                team_assignment[tid] = random.choice(opts)
        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _crossover(
        self, p1: Individual, p2: Individual
    ) -> Tuple[Individual, Individual]:
        def ox(parent1_seq, parent2_seq):
            n = len(parent1_seq)
            if n < 2:
                return list(parent1_seq)
            cx1, cx2 = sorted(random.sample(range(n), 2))
            child = [None] * n
            child[cx1 : cx2 + 1] = parent1_seq[cx1 : cx2 + 1]
            used = set(child[cx1 : cx2 + 1])
            pos = (cx2 + 1) % n
            for gene in parent2_seq:
                if gene not in used:
                    while child[pos] is not None:
                        pos = (pos + 1) % n
                    child[pos] = gene
                    pos = (pos + 1) % n
            return child

        c1_order = ox(p1.task_order, p2.task_order)
        c2_order = ox(p2.task_order, p1.task_order)

        c1_teams = list(p1.team_assignment)
        c2_teams = list(p2.team_assignment)

        for i in range(self.num_tasks):
            if random.random() < 0.5:
                c1_teams[i], c2_teams[i] = p2.team_assignment[i], p1.team_assignment[i]

        return (
            Individual(task_order=c1_order, team_assignment=c1_teams),
            Individual(task_order=c2_order, team_assignment=c2_teams),
        )

    def _mutate(self, ind: Individual) -> Individual:
        order = list(ind.task_order)
        teams = list(ind.team_assignment)

        if len(order) >= 2 and random.random() < 0.5:
            i, j = random.sample(range(len(order)), 2)
            order[i], order[j] = order[j], order[i]

        if random.random() < 0.5 and self.tasks_with_teams:
            tid = random.choice(self.tasks_with_teams)
            opts = self.compatible_teams_indices[tid]
            if len(opts) > 1:
                current = teams[tid]
                others = [t for t in opts if t != current]
                if others:
                    teams[tid] = random.choice(others)

        return Individual(task_order=order, team_assignment=teams)

    def run(
        self,
        problem: ProblemInstance,
        next_runnable,  # Typing omitted to avoid circular import issues if any
        time_limit: float = float("inf"),
    ) -> Schedule:
        result = next_runnable.run(problem, time_limit=time_limit)

        # Now run GA with remaining time?
        # Ideally, we split the budget. But `Pipeline` budget logic does that BEFORE calling run.
        # So `time_limit` passed here IS the budget for this middleware?
        # No, `_BudgetedMiddlewareRunnable` passes `m_budget` as `time_limit` to `middleware.run`.
        # So `time_limit` IS the budget for ME.
        # But `MapResult.run` passes `time_limit` to `next_runnable`!
        # This means `next_runnable` consumes MY budget?
        # In `Pipeline`:
        # `pipeline = _BudgetedMiddlewareRunnable(m, pipeline, m_budget)`
        # `m` is `ga_search`. `pipeline` (inner) is the solver (or next middleware).
        # `m.run` is called with `m_budget`.
        # `m.run` calls `next_runnable.run` with `m_budget`.
        # This seems wrong if `m_budget` was intended ONLY for `m`.
        # If `m_budget` is for `m`, we shouldn't pass it to `next_runnable`.
        # `next_runnable` should have its OWN budget wrapped around it?
        # In `Pipeline`, `pipeline` (the inner runnable) IS already wrapped with its budget:
        # `pipeline = _BudgetedRunnable(self.solver, solver_budget)`
        # So when `m.run` calls `pipeline.run(..., time_limit=...)`, the `_BudgetedRunnable` ignores the passed `time_limit` and uses `self.budget`.
        # So `time_limit` passed to `m.run` IS available for `m` to use!
        # So I can just use `time_limit` in `ga_search`.

        # So I will override `run` to use `time_limit`.

        self._preprocess(problem)
        random.seed(self.seed)

        if not self.tasks_with_teams:
            return result

        with TimeBudget(time_limit) as budget:
            population: List[Individual] = []

            # Inject the result from the previous solver
            population.append(self._schedule_to_individual(result))

            for _ in range(self.initial_population_size - 1):
                if budget.is_expired():
                    break
                population.append(self._generate_random_individual())

            if not population:
                population.append(self._generate_random_individual())

            best_ind = population[0]
            best_score = self._evaluate(best_ind)

            generation = 0
            while not budget.is_expired() and generation < self.max_generation:
                generation += 1
                population.sort(key=lambda x: self._evaluate(x))
                current_best = population[0]
                current_score = self._evaluate(current_best)

                if current_score < best_score:
                    best_score = current_score
                    best_ind = current_best

                num_best = max(len(population) // 2, 2)
                parents = population[:num_best]
                next_pop = list(population)

                for _ in range(num_best):
                    if budget.is_expired():
                        break
                    p1, p2 = random.sample(parents, 2)
                    c1, c2 = self._crossover(p1, p2)
                    next_pop.append(c1)
                    next_pop.append(c2)

                for _ in range(num_best):
                    if budget.is_expired():
                        break
                    p = random.choice(parents)
                    next_pop.append(self._mutate(p))

                population = next_pop
                if len(population) > self.max_population_size:
                    population.sort(key=lambda x: self._evaluate(x))
                    population = population[: self.initial_population_size]

        raw_assignments = self._decode(best_ind)
        final_assignments = []
        for a in raw_assignments:
            real_team_id = self.team_idx_to_id[a.team_id]
            final_assignments.append(
                Assignment(
                    task_id=a.task_id, team_id=real_team_id, start_time=a.start_time
                )
            )
        return Schedule(assignments=final_assignments)

    def map_result(self, problem: ProblemInstance, result: Schedule) -> Schedule:
        # This won't be called if we override run()
        return result
