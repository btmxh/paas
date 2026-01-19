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
        self.compatible_teams_indices: List[List[int]] = []
        self.team_costs: List[List[int]] = []  # matrix [task_id][team_idx]
        self.team_initial_availability: List[int] = []
        self.team_idx_to_id: List[int] = []
        self.tasks_with_teams: List[int] = []

    def _preprocess(self, problem: ProblemInstance):
        """Prepare internal data structures for fast access."""
        self.num_tasks = problem.num_tasks
        self.num_teams = problem.num_teams

        # Map teams to 0..M-1
        self.team_idx_to_id = sorted(problem.teams.keys())
        team_id_to_idx = {tid: i for i, tid in enumerate(self.team_idx_to_id)}

        self.team_initial_availability = [
            problem.teams[tid].available_from for tid in self.team_idx_to_id
        ]

        # Process tasks
        # Assumption: Task IDs are 0..N-1.
        # Verify assumption lightly (check max ID)
        if problem.tasks:
            max_task_id = max(problem.tasks.keys())
            if max_task_id >= self.num_tasks:
                # If IDs are not continuous, this optimization breaks.
                # But we assume ContinuousIndexer is used.
                # If N=10 and max_id=100, we'd need a huge array.
                # For safety, let's use max_task_id + 1 as array size, but warn?
                # The user explicitly said "using this assumption", so we trust it.
                pass

        self.durations = [0] * self.num_tasks
        self.predecessors = [[] for _ in range(self.num_tasks)]
        self.compatible_teams_indices = [[] for _ in range(self.num_tasks)]
        # Use a large number for incompatible cost
        INF = 10**12
        self.team_costs = [[INF] * self.num_teams for _ in range(self.num_tasks)]

        self.tasks_with_teams = []

        for tid, task in problem.tasks.items():
            if tid >= self.num_tasks:
                # Should not happen if assumption holds
                continue
            
            self.durations[tid] = task.duration
            # Predecessors: assume they are also valid indices
            self.predecessors[tid] = task.predecessors

            if task.compatible_teams:
                self.tasks_with_teams.append(tid)
                
            for team_id, cost in task.compatible_teams.items():
                if team_id in team_id_to_idx:
                    t_idx = team_id_to_idx[team_id]
                    self.compatible_teams_indices[tid].append(t_idx)
                    self.team_costs[tid][t_idx] = cost

    def _decode(self, individual: Individual) -> List[Assignment]:
        """
        Decode using array lookups.
        """
        # team_available: array of size M
        team_available = list(self.team_initial_availability)
        
        # task_finish_times: array of size N, initialized to -1 (not finished)
        task_finish_times = [-1] * self.num_tasks

        assignments: List[Assignment] = []
        
        # Optimization: Use a list for todo instead of creating new lists
        # But we need to check dependencies.
        # For a valid topological sort, we can just iterate. 
        # But the GA generates arbitrary permutations.
        # We must skip tasks whose predecessors are not ready.
        
        todo = individual.task_order
        # todo is a list of task IDs.
        
        # We need to iterate until all possible tasks are scheduled.
        # Since checking dependencies can be slow if we scan the whole list repeatedly.
        # Ideally, we'd maintain in-degree, but that depends on order? No, dependencies are fixed.
        # But we want to respect the order in `todo` as a priority.
        
        # Standard approach: iterate through todo, pick first available, remove, repeat.
        # Optimized:
        # Keep a set/boolean array of finished tasks? `task_finish_times[p] != -1` is enough.
        
        # Since 'todo' can be large, scanning it repeatedly is O(N^2).
        # Can we do better?
        # The gene defines a *priority*.
        # We can try to schedule in the order of the gene. 
        # If a task is not ready, we delay it.
        # Actually, the standard "permutation decoding" for scheduling usually means:
        # "Take tasks in the order they appear in the chromosome. If ready, schedule. If not, wait?"
        # If we skip and come back, that's complex.
        # 
        # Alternative Interpretation: The chromosome represents a Topological Sort?
        # If we enforce the chromosome to be a valid topological sort, decoding is O(N).
        # But GA operations destroy topological property.
        #
        # A common approach is: The chromosome is a priority list.
        # We simulate:
        # Set of ready tasks S (initially those with no preds).
        # But we have a priority list P.
        # Pick the first task in P that is in S. Schedule it. Update S. Remove from P.
        # This is O(N^2) if naive.
        
        # For this implementation, let's stick to the previous logic but with array lookups.
        # It handles the "wait for predecessors" by repeated scanning.
        
        pending = list(todo) # Copy
        
        # We can optimize the check by remembering where we left off? 
        # No, because a task later in the list might unblock a task earlier.
        
        while pending:
            progress = False
            next_pending = []
            
            for task_id in pending:
                # Check predecessors
                preds = self.predecessors[task_id]
                preds_done = True
                preds_complete_time = 0
                
                for p in preds:
                    ft = task_finish_times[p]
                    if ft == -1:
                        preds_done = False
                        break
                    if ft > preds_complete_time:
                        preds_complete_time = ft
                
                if not preds_done:
                    next_pending.append(task_id)
                    continue

                # Schedule
                team_idx = individual.team_assignment[task_id]
                
                # Check if compatible (in case mutation messed up, though we should control mutation)
                # But for speed we assume valid team_idx if we control generation.
                # However, if team_idx is not compatible (cost INF), we should penalize or skip?
                # The fitness function handles cost. Here we just schedule.
                # If cost is INF, it will be penalized.
                
                start_time = max(team_available[team_idx], preds_complete_time)
                duration = self.durations[task_id]
                finish_time = start_time + duration
                
                # Record assignment
                # We need original team ID for the final output, but for fitness we don't.
                # We defer creating Assignment objects until final output if possible?
                # But _evaluate needs them.
                # Let's create a lightweight struct or tuple? 
                # Actually, _evaluate only needs counts and times.
                
                task_finish_times[task_id] = finish_time
                team_available[team_idx] = finish_time
                
                # For fitness calculation, we need to know we scheduled it.
                # We can construct assignments list.
                assignments.append(Assignment(task_id, team_idx, start_time))
                
                progress = True
            
            if not progress:
                # Deadlock or cycle (should not happen if input is DAG)
                break
            
            pending = next_pending
            
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
        team_available = list(self.team_initial_availability)
        task_finish_times = [-1] * self.num_tasks
        
        task_order = []
        team_assignment = [0] * self.num_tasks
        
        remaining = set(self.tasks_with_teams)
        
        while remaining:
            best_task = -1
            best_team_idx = -1
            best_start = sys.maxsize
            best_cost = sys.maxsize
            
            for tid in remaining:
                # Check preds
                preds_done = True
                pred_done_time = 0
                for p in self.predecessors[tid]:
                    ft = task_finish_times[p]
                    if ft == -1:
                        preds_done = False
                        break
                    if ft > pred_done_time:
                        pred_done_time = ft
                
                if not preds_done:
                    continue
                
                # Check teams
                for team_idx in self.compatible_teams_indices[tid]:
                    cost = self.team_costs[tid][team_idx]
                    start = max(team_available[team_idx], pred_done_time)
                    
                    if start < best_start or (start == best_start and cost < best_cost):
                        best_start = start
                        best_task = tid
                        best_team_idx = team_idx
                        best_cost = cost
            
            if best_task == -1:
                 # Fill remaining
                 for tid in remaining:
                     task_order.append(tid)
                     opts = self.compatible_teams_indices[tid]
                     if opts:
                         team_assignment[tid] = opts[0]
                 break
            
            task_order.append(best_task)
            team_assignment[best_task] = best_team_idx
            finish = best_start + self.durations[best_task]
            task_finish_times[best_task] = finish
            team_available[best_team_idx] = finish
            remaining.remove(best_task)
            
        return Individual(task_order=task_order, team_assignment=team_assignment)

    def _crossover(self, p1: Individual, p2: Individual) -> Tuple[Individual, Individual]:
        # Order crossover
        n_order = len(p1.task_order)
        # Using the same logic as before but adapted for class methods if needed, 
        # or just inline/helper.
        
        # Helper for OX
        def ox(parent1_seq, parent2_seq):
            n = len(parent1_seq)
            if n < 2: return list(parent1_seq)
            cx1, cx2 = sorted(random.sample(range(n), 2))
            child = [None] * n
            child[cx1:cx2+1] = parent1_seq[cx1:cx2+1]
            used = set(child[cx1:cx2+1])
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
            Individual(task_order=c2_order, team_assignment=c2_teams)
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
                if budget.is_expired(): break
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
                
                next_pop = list(population) # Keep old ones? Or just parents?
                # Usually we replace. But let's keep parents + offspring + elitism.
                # The code before did: new_pop = list(population) -> appended children.
                # This grows population. Then trimmed at end.
                
                # Crossover
                for _ in range(num_best):
                    if budget.is_expired(): break
                    p1, p2 = random.sample(parents, 2)
                    c1, c2 = self._crossover(p1, p2)
                    next_pop.append(c1)
                    next_pop.append(c2)
                
                # Mutation
                for _ in range(num_best):
                    if budget.is_expired(): break
                    p = random.choice(parents)
                    next_pop.append(self._mutate(p))
                
                population = next_pop
                
                # Trim
                if len(population) > self.max_population_size:
                    population.sort(key=lambda x: self._evaluate(x))
                    population = population[:self.initial_population_size] # Shrink back to initial size
        
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
            final_assignments.append(Assignment(
                task_id=a.task_id,
                team_id=real_team_id,
                start_time=a.start_time
            ))
            
        return Schedule(assignments=final_assignments)