import sys
import random
import heapq
from dataclasses import dataclass
from typing import List, Tuple, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver
from paas.time_budget import TimeBudget


@dataclass
class Individual:
    """
    Chromosome encoding:
    - task_order: List[int] - permutation of task IDs (0..N-1)
    - team_assignment: List[int] - index is task_id, value is team_idx (0..M-1)
    - fitness: cached fitness score (computed lazily)
    """

    task_order: List[int]
    team_assignment: List[int]
    fitness: Optional[Tuple[int, int, int]] = None


class GASolver(Solver):
    """
    Genetic Algorithm based solver for the Project Assignment and Scheduling (PaaS) problem.
     Optimized assuming:
    1. Task IDs are continuous integers 0..N-1 (provided by ContinuousIndexer).
    2. Team IDs are mapped to 0..M-1 internally.
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
        self.team_costs: List[List[int]] = []  # matrix [task_id][team_idx]
        self.team_initial_availability: List[int] = []
        self.team_idx_to_id: List[int] = []
        self.tasks_with_teams: List[int] = []

    def _preprocess(self, problem: ProblemInstance):
        """
        Prepare internal data structures for fast access.

        Optimized for ContinuousIndexer:
        - Assumes Task keys are integers 0..N-1
        - Assumes Team keys are integers 0..M-1
        """
        problem.assert_continuous_indices()
        self.num_tasks = problem.num_tasks
        self.num_teams = problem.num_teams

        # 1. Team Availability
        # Since team keys are 0..M-1, we can map directly to list indices.
        # We create a list where index `i` corresponds to team ID `i`.
        self.team_initial_availability = [0] * self.num_teams
        for tid, team in problem.teams.items():
            self.team_initial_availability[tid] = team.available_from

        # We keep this for the 'run' method's final reconstruction step,
        # ensuring it maps index i -> ID i.
        self.team_idx_to_id = list(range(self.num_teams))

        # 2. Task Data Structures (Pre-allocate for speed)
        self.durations = [0] * self.num_tasks
        self.predecessors = [[] for _ in range(self.num_tasks)]
        self.successors = [[] for _ in range(self.num_tasks)]
        self.initial_in_degrees = [0] * self.num_tasks
        self.compatible_teams_indices = [[] for _ in range(self.num_tasks)]

        # Use a large number for incompatible cost (Infinity)
        INF = 10**12
        self.team_costs = [[INF] * self.num_teams for _ in range(self.num_tasks)]
        self.tasks_with_teams = []

        # 3. Flatten Task Data
        for tid, task in problem.tasks.items():
            # Direct index access (No dictionary lookups or bounds checking needed)
            self.durations[tid] = task.duration
            self.predecessors[tid] = task.predecessors
            self.successors[tid] = task.successors
            self.initial_in_degrees[tid] = len(task.predecessors)

            if task.compatible_teams:
                self.tasks_with_teams.append(tid)

            # Flatten compatibility map
            # key `team_idx` is already an integer 0..M-1
            for team_idx, cost in task.compatible_teams.items():
                self.compatible_teams_indices[tid].append(team_idx)
                self.team_costs[tid][team_idx] = cost

    def _decode(self, individual: Individual) -> List[Assignment]:
        """
        Decode using topological sort with priority queue.
        Resolves dependencies efficiently (O(N log N)).
        """
        # Map task_id -> priority (index in task_order)
        # Lower index = higher priority
        priority = [0] * self.num_tasks
        for rank, tid in enumerate(individual.task_order):
            priority[tid] = rank

        # Setup simulation state
        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        current_in_degrees = list(self.initial_in_degrees)

        assignments: List[Assignment] = []

        # Priority queue stores (rank, task_id)
        # We only add tasks that are ready (in_degree == 0)
        ready_heap = []
        for tid in self.tasks_with_teams:
            if current_in_degrees[tid] == 0:
                heapq.heappush(ready_heap, (priority[tid], tid))

        while ready_heap:
            _, task_id = heapq.heappop(ready_heap)

            team_idx = individual.team_assignment[task_id]

            # Determine start time based on dependencies
            preds_complete_time = 0
            for p in self.predecessors[task_id]:
                # p must be finished because we only process when in_degree=0
                # and we process in dependency order.
                p_finish = task_finish_times[p]
                if p_finish > preds_complete_time:
                    preds_complete_time = p_finish

            start_time = max(team_available[team_idx], preds_complete_time)
            duration = self.durations[task_id]
            finish_time = start_time + duration

            task_finish_times[task_id] = finish_time
            team_available[team_idx] = finish_time

            assignments.append(Assignment(task_id, team_idx, start_time))

            # Unlock successors
            for s in self.successors[task_id]:
                current_in_degrees[s] -= 1
                if current_in_degrees[s] == 0:
                    # Only add if it's a schedulable task (in tasks_with_teams)
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
            # a.team_id is team_idx here
            # a.task_id is task_idx here

            duration = self.durations[a.task_id]
            finish = a.start_time + duration
            if finish > completion_time:
                completion_time = finish

            cost = self.team_costs[a.task_id][a.team_id]
            total_cost += cost

        individual.fitness = (-task_count, completion_time, total_cost)
        return individual.fitness

    def _generate_random_individual(self) -> Individual:
        # task_order: permutation of tasks_with_teams
        task_order = list(self.tasks_with_teams)
        random.shuffle(task_order)

        # team_assignment: array of size N
        # For tasks not in tasks_with_teams, value doesn't matter (say -1 or 0)
        team_assignment = [0] * self.num_tasks

        for tid in self.tasks_with_teams:
            opts = self.compatible_teams_indices[tid]
            if opts:
                team_assignment[tid] = random.choice(opts)

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _generate_greedy_individual(self) -> Individual:
        # Array based greedy
        # We need to reimplement this because the old one relied on iterative scanning.
        # But we can also use the heap-based approach here implicitly?
        # Actually, greedy construction usually builds the order AND assignment dynamically.
        # But we need to return an Individual (task_order, team_assignment).
        # We can construct the order by appending tasks as we pick them.

        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        current_in_degrees = list(self.initial_in_degrees)

        task_order = []
        team_assignment = [0] * self.num_tasks

        # Candidates are tasks with in_degree 0
        # We don't have a priority yet, we want to FIND the best one.
        # So we just keep a set of candidates.
        candidates = set()
        for tid in self.tasks_with_teams:
            if current_in_degrees[tid] == 0:
                candidates.add(tid)

        processed_count = 0
        total_tasks = len(self.tasks_with_teams)

        while candidates:
            best_task = -1
            best_team_idx = -1
            best_start = sys.maxsize
            best_cost = sys.maxsize

            # Evaluate all candidates
            for tid in candidates:
                # Preds are guaranteed done
                pred_done_time = 0
                for p in self.predecessors[tid]:
                    ft = task_finish_times[p]
                    if ft > pred_done_time:
                        pred_done_time = ft

                for team_idx in self.compatible_teams_indices[tid]:
                    cost = self.team_costs[tid][team_idx]
                    start = max(team_available[team_idx], pred_done_time)

                    if start < best_start or (start == best_start and cost < best_cost):
                        best_start = start
                        best_task = tid
                        best_team_idx = team_idx
                        best_cost = cost

            if best_task == -1:
                # Should not happen if DAG is valid and candidates exist
                # But if no candidates found (e.g. all compatible teams blocked? No, waiting is allowed)
                # If best_task stays -1, it means candidates was empty? No, loop runs if candidates not empty.
                # Maybe compatible_teams_indices is empty for a task?
                # tasks_with_teams only includes tasks with compatible teams.
                break

            task_order.append(best_task)
            team_assignment[best_task] = best_team_idx

            finish = best_start + self.durations[best_task]
            task_finish_times[best_task] = finish
            team_available[best_team_idx] = finish

            candidates.remove(best_task)
            processed_count += 1

            # Unlock successors
            for s in self.successors[best_task]:
                current_in_degrees[s] -= 1
                if current_in_degrees[s] == 0:
                    if self.compatible_teams_indices[s]:
                        candidates.add(s)

        # If not all tasks scheduled (e.g. disconnected components or logic error?), fill remainder
        if processed_count < total_tasks:
            remaining = set(self.tasks_with_teams) - set(task_order)
            for tid in remaining:
                task_order.append(tid)
                opts = self.compatible_teams_indices[tid]
                if opts:
                    team_assignment[tid] = opts[0]

        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _crossover(
        self, p1: Individual, p2: Individual
    ) -> Tuple[Individual, Individual]:
        # Order crossover
        # Using the same logic as before but adapted for class methods if needed,
        # or just inline/helper.

        # Helper for OX
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

        # Team crossover: Uniform
        # team_assignment is a List[int] of size N
        # We only care about entries for tasks_with_teams?
        # Yes, but it's simpler to cross the whole array.
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

        # Order swap
        if len(order) >= 2 and random.random() < 0.5:
            i, j = random.sample(range(len(order)), 2)
            order[i], order[j] = order[j], order[i]

        # Team mutation
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
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        self._preprocess(problem)
        random.seed(self.seed)

        if not self.tasks_with_teams:
            return Schedule(assignments=[])

        with TimeBudget(time_limit) as budget:
            population: List[Individual] = []

            population.append(self._generate_greedy_individual())

            for _ in range(self.initial_population_size - 1):
                if budget.is_expired():
                    break
                population.append(self._generate_random_individual())

            if not population:
                # Fallback if time extremely short
                population.append(self._generate_random_individual())

            best_ind = population[0]
            best_score = self._evaluate(best_ind)

            generation = 0
            while not budget.is_expired() and generation < self.max_generation:
                generation += 1

                # Evaluate
                # (Already evaluated or lazy)
                population.sort(key=lambda x: self._evaluate(x))

                current_best = population[0]
                current_score = self._evaluate(current_best)

                if current_score < best_score:
                    best_score = current_score
                    best_ind = current_best

                # Selection
                num_best = max(len(population) // 2, 2)
                parents = population[:num_best]

                next_pop = list(population)  # Keep old ones? Or just parents?
                # Usually we replace. But let's keep parents + offspring + elitism.
                # The code before did: new_pop = list(population) -> appended children.
                # This grows population. Then trimmed at end.

                # Crossover
                for _ in range(num_best):
                    if budget.is_expired():
                        break
                    p1, p2 = random.sample(parents, 2)
                    c1, c2 = self._crossover(p1, p2)
                    next_pop.append(c1)
                    next_pop.append(c2)

                # Mutation
                for _ in range(num_best):
                    if budget.is_expired():
                        break
                    p = random.choice(parents)
                    next_pop.append(self._mutate(p))

                population = next_pop

                # Trim
                if len(population) > self.max_population_size:
                    population.sort(key=lambda x: self._evaluate(x))
                    population = population[
                        : self.initial_population_size
                    ]  # Shrink back to initial size

        # Decode best to assignments with original IDs
        raw_assignments = self._decode(best_ind)
        final_assignments = []
        for a in raw_assignments:
            # map team_idx back to team_id
            # task_id is already original_id (since we assumed input is 0..N-1 and output is 0..N-1)
            # wait, if input was reindexed by Middleware, then we return reindexed IDs.
            # The middleware maps them back.
            # So here we just return what we have (indices), EXCEPT for team IDs.
            # Middleware does NOT reindex teams. So we must map team_idx -> team_id.

            real_team_id = self.team_idx_to_id[a.team_id]
            final_assignments.append(
                Assignment(
                    task_id=a.task_id, team_id=real_team_id, start_time=a.start_time
                )
            )

        return Schedule(assignments=final_assignments)
