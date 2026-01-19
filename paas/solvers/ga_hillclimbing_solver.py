"""
GA + Hill Climbing Solver (Memetic Algorithm).

This combines Genetic Algorithm with Local Search (Hill Climbing):
1. GA explores the solution space globally (exploration)
2. Hill Climbing refines promising solutions locally (exploitation)

Hill Climbing is applied to the best individual after GA finishes.
"""

import sys
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver
from paas.time_budget import TimeBudget


@dataclass
class Individual:
    """
    Chromosome encoding:
    - task_order: permutation of task IDs (scheduling order)
    - team_assignment: dict mapping task_id -> team_id
    - fitness: cached fitness score
    """

    task_order: List[int]
    team_assignment: Dict[int, int]
    fitness: Optional[Tuple[int, int, int]] = None


class GAHillClimbingSolver(Solver):
    """
    Memetic Algorithm: GA + Hill Climbing for the PaaS problem.

    Combines:
    - GA: global exploration via selection, crossover, mutation
    - Hill Climbing: local exploitation to refine best solutions

    Hill Climbing Neighborhood:
    1. Swap: exchange positions of two tasks in task_order
    2. Team change: assign a different team to a task

    Strategy: First-improvement (accept first better neighbor found)

    Optimizes (in priority order):
    1. Maximal number of tasks scheduled
    2. Minimal completion time (makespan)
    3. Minimal total cost
    """

    def __init__(
        self,
        initial_population_size: int = 50,
        max_population_size: int = 200,
        seed: int = 8,
        time_factor: float = 1.0,
        hill_climbing_iterations: int = 10,
    ):
        super().__init__(time_factor)
        self.initial_population_size = initial_population_size
        self.max_population_size = max_population_size
        self.seed = seed
        self.hill_climbing_iterations = hill_climbing_iterations

    def _decode(
        self, individual: Individual, problem: ProblemInstance
    ) -> List[Assignment]:
        """Decode an individual into assignments."""
        scheduled_finishes: Dict[int, int] = {}
        assignments: List[Assignment] = []
        team_available = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        todo = list(individual.task_order)

        progress = True
        while progress and todo:
            progress = False
            new_todo = []
            for task_id in todo:
                if task_id in scheduled_finishes:
                    continue

                task = problem.tasks[task_id]
                team_id = individual.team_assignment[task_id]

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
                    new_todo.append(task_id)
                    continue

                start_time = max(team_available[team_id], preds_complete_time)
                assignments.append(Assignment(task_id, team_id, start_time))
                finish_time = start_time + task.duration
                scheduled_finishes[task_id] = finish_time
                team_available[team_id] = finish_time
                progress = True
            todo = new_todo
        return assignments

    def _evaluate(
        self, individual: Individual, problem: ProblemInstance
    ) -> Tuple[int, int, int]:
        """Returns: (-task_count, completion_time, cost) for minimization."""
        if individual.fitness is not None:
            return individual.fitness

        assignments = self._decode(individual, problem)

        if not assignments:
            return (0, sys.maxsize, sys.maxsize)

        task_count = len(assignments)
        completion_time = 0
        total_cost = 0

        for a in assignments:
            task = problem.tasks[a.task_id]
            completion_time = max(completion_time, a.start_time + task.duration)
            total_cost += task.compatible_teams.get(a.team_id, 10**12)

        individual.fitness = (-task_count, completion_time, total_cost)
        return individual.fitness

    def _generate_random_individual(
        self, problem: ProblemInstance, tasks_with_teams: List[int]
    ) -> Individual:
        """Generate a random individual."""
        task_order = list(tasks_with_teams)
        random.shuffle(task_order)

        team_assignment = {}
        for tid in tasks_with_teams:
            task = problem.tasks[tid]
            team_assignment[tid] = random.choice(list(task.compatible_teams.keys()))

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _generate_greedy_individual(
        self, problem: ProblemInstance, tasks_with_teams: List[int]
    ) -> Individual:
        """Generate an individual using greedy heuristic."""
        tasks = problem.tasks
        teams = problem.teams

        team_available = {tid: team.available_from for tid, team in teams.items()}
        task_completion: Dict[int, int] = {}

        task_order: List[int] = []
        team_assignment: Dict[int, int] = {}

        remaining = set(tasks_with_teams)

        while remaining:
            best_task = -1
            best_team = -1
            best_start = sys.maxsize
            best_cost = sys.maxsize

            for tid in remaining:
                task = tasks[tid]
                if not all(p in task_completion for p in task.predecessors):
                    continue

                pred_done_time = max(
                    (task_completion[p] for p in task.predecessors), default=0
                )

                for team_id, cost in task.compatible_teams.items():
                    start = max(team_available[team_id], pred_done_time)
                    if start < best_start or (start == best_start and cost < best_cost):
                        best_start = start
                        best_task = tid
                        best_team = team_id
                        best_cost = cost

            if best_task == -1:
                for tid in remaining:
                    task_order.append(tid)
                    task = tasks[tid]
                    team_assignment[tid] = list(task.compatible_teams.keys())[0]
                break

            task_order.append(best_task)
            team_assignment[best_task] = best_team
            task_completion[best_task] = best_start + tasks[best_task].duration
            team_available[best_team] = task_completion[best_task]
            remaining.remove(best_task)

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _crossover_order(
        self, p1: List[int], p2: List[int]
    ) -> Tuple[List[int], List[int]]:
        """Order Crossover (OX)."""
        n = len(p1)
        if n < 2:
            return list(p1), list(p2)

        cx1, cx2 = sorted(random.sample(range(n), 2))

        def make_child(parent1: List[int], parent2: List[int]) -> List[int]:
            child: List[Optional[int]] = [None] * n
            child[cx1 : cx2 + 1] = parent1[cx1 : cx2 + 1]
            used = set(child[cx1 : cx2 + 1])

            pos = (cx2 + 1) % n
            for gene in parent2:
                if gene not in used:
                    while child[pos] is not None:
                        pos = (pos + 1) % n
                    child[pos] = gene
                    pos = (pos + 1) % n
            return [x for x in child if x is not None]

        return make_child(p1, p2), make_child(p2, p1)

    def _crossover_teams(
        self, t1: Dict[int, int], t2: Dict[int, int]
    ) -> Tuple[Dict[int, int], Dict[int, int]]:
        """Uniform crossover for team assignments."""
        child1, child2 = {}, {}
        for tid in t1:
            if random.random() < 0.5:
                child1[tid], child2[tid] = t1[tid], t2[tid]
            else:
                child1[tid], child2[tid] = t2[tid], t1[tid]
        return child1, child2

    def _crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """Crossover two individuals."""
        order1, order2 = self._crossover_order(parent1.task_order, parent2.task_order)
        teams1, teams2 = self._crossover_teams(
            parent1.team_assignment, parent2.team_assignment
        )

        return (
            Individual(task_order=order1, team_assignment=teams1),
            Individual(task_order=order2, team_assignment=teams2),
        )

    def _mutate(self, parent: Individual, problem: ProblemInstance) -> Individual:
        """Mutate an individual."""
        task_order = list(parent.task_order)
        team_assignment = dict(parent.team_assignment)

        if len(task_order) >= 2 and random.random() < 0.5:
            i, j = random.sample(range(len(task_order)), 2)
            task_order[i], task_order[j] = task_order[j], task_order[i]

        if random.random() < 0.5:
            tid = random.choice(list(team_assignment.keys()))
            task = problem.tasks[tid]
            possible_teams = list(task.compatible_teams.keys())
            if len(possible_teams) > 1:
                other_teams = [t for t in possible_teams if t != team_assignment[tid]]
                if other_teams:
                    team_assignment[tid] = random.choice(other_teams)

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _hill_climbing(
        self, individual: Individual, problem: ProblemInstance, max_iter: int
    ) -> Individual:
        """
        Hill Climbing (Local Search) to improve an individual.

        Neighborhood moves:
        1. Swap: exchange positions of two tasks in task_order
        2. Team change: assign a different team to a task

        Strategy: First-improvement (accept first better neighbor)
        """
        current = individual
        current_score = self._evaluate(current, problem)

        for _ in range(max_iter):
            improved = False

            # Try swap neighbors
            n = len(current.task_order)
            if n >= 2:
                for _ in range(min(n * 2, 20)):
                    i, j = random.sample(range(n), 2)

                    new_order = list(current.task_order)
                    new_order[i], new_order[j] = new_order[j], new_order[i]
                    neighbor = Individual(
                        task_order=new_order,
                        team_assignment=dict(current.team_assignment),
                    )
                    neighbor_score = self._evaluate(neighbor, problem)

                    # First-improvement: accept immediately if better
                    if neighbor_score < current_score:
                        current = neighbor
                        current_score = neighbor_score
                        improved = True
                        break

            # Try team change neighbors if no swap improvement
            if not improved:
                task_ids = list(current.team_assignment.keys())
                random.shuffle(task_ids)

                for tid in task_ids[:10]:
                    task = problem.tasks[tid]
                    current_team = current.team_assignment[tid]
                    other_teams = [
                        t for t in task.compatible_teams.keys() if t != current_team
                    ]

                    for new_team in other_teams:
                        new_assignment = dict(current.team_assignment)
                        new_assignment[tid] = new_team
                        neighbor = Individual(
                            task_order=list(current.task_order),
                            team_assignment=new_assignment,
                        )
                        neighbor_score = self._evaluate(neighbor, problem)

                        if neighbor_score < current_score:
                            current = neighbor
                            current_score = neighbor_score
                            improved = True
                            break
                    if improved:
                        break

            # No improvement found - local optimum reached
            if not improved:
                break

        return current

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        random.seed(self.seed)

        tasks_with_teams = [
            tid for tid, task in problem.tasks.items() if task.compatible_teams
        ]

        if not tasks_with_teams:
            return Schedule(assignments=[])

        with TimeBudget(time_limit) as budget:
            # Initialize population
            population: List[Individual] = []

            greedy_ind = self._generate_greedy_individual(problem, tasks_with_teams)
            population.append(greedy_ind)

            for _ in range(self.initial_population_size - 1):
                if budget.is_expired():
                    break
                population.append(
                    self._generate_random_individual(problem, tasks_with_teams)
                )

            best_individual = population[0]
            best_score = self._evaluate(best_individual, problem)

            # Main GA loop
            while not budget.is_expired():
                if not population:
                    break

                population.sort(key=lambda x: self._evaluate(x, problem))

                current_best_score = self._evaluate(population[0], problem)
                if current_best_score < best_score:
                    best_score = current_best_score
                    best_individual = population[0]

                num_best = max(len(population) // 2, 2)
                best_population = population[:num_best]

                new_pop = list(population)

                # Crossover
                for _ in range(num_best):
                    if budget.is_expired():
                        break
                    if len(best_population) < 2:
                        break

                    p1, p2 = random.sample(best_population, 2)
                    c1, c2 = self._crossover(p1, p2)
                    new_pop.append(c1)
                    new_pop.append(c2)

                # Mutation
                for _ in range(num_best):
                    if budget.is_expired():
                        break

                    p = random.choice(best_population)
                    mchild = self._mutate(p, problem)
                    new_pop.append(mchild)

                population = new_pop
                population.append(best_individual)

                if len(population) > self.max_population_size:
                    population.sort(key=lambda x: self._evaluate(x, problem))
                    population = population[: self.initial_population_size]

            # Apply Hill Climbing to best individual
            if self.hill_climbing_iterations > 0:
                best_individual = self._hill_climbing(
                    best_individual, problem, self.hill_climbing_iterations
                )

            return Schedule(assignments=self._decode(best_individual, problem))
