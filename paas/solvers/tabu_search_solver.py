import sys
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver
from paas.time_budget import TimeBudget


@dataclass
class Solution:
    """
    Represents a candidate solution in the search space.

    Attributes:
        task_order: Sequence defining the scheduling priority of tasks.
        team_assignment: Mapping from each task to its assigned team.
        fitness: Cached objective values to avoid redundant computation.
    """

    task_order: List[int]
    team_assignment: Dict[int, int]
    fitness: Optional[Tuple[int, int, int]] = None


@dataclass
class Move:
    """
    Encapsulates a neighborhood transition for the tabu mechanism.

    Attributes:
        move_type: Either 'swap' (reorder tasks) or 'team' (reassign resource).
        task_id_1: Primary task involved in the move.
        task_id_2: Secondary task (for swap) or target team (for reassignment).
    """

    move_type: str
    task_id_1: int
    task_id_2: int = -1

    def __hash__(self):
        return hash((self.move_type, self.task_id_1, self.task_id_2))

    def __eq__(self, other):
        return (self.move_type, self.task_id_1, self.task_id_2) == (
            other.move_type,
            other.task_id_1,
            other.task_id_2,
        )


class TabuSearchSolver(Solver):
    """
    Metaheuristic solver implementing Tabu Search for task scheduling.

    This solver navigates the solution space through iterative neighborhood
    exploration while maintaining short-term memory (tabu list) to prevent
    cycling and promote diversification.

    The algorithm balances intensification (local improvement) with
    diversification (escaping local optima) through:
        - Adaptive neighborhood generation
        - Aspiration criteria for promising forbidden moves
        - Stochastic restart upon stagnation

    Objective hierarchy (lexicographic ordering):
        1. Maximize scheduled task count
        2. Minimize project makespan
        3. Minimize total assignment cost
    """

    def __init__(
        self,
        tabu_tenure: int = 10,
        max_neighbors: int = 50,
        seed: int = 42,
        time_factor: float = 1.0,
    ):
        """
        Initialize the Tabu Search solver with configurable parameters.

        Args:
            tabu_tenure: Duration (in iterations) that a move remains forbidden.
            max_neighbors: Neighborhood sample size per iteration.
            seed: RNG seed for deterministic behavior.
            time_factor: Multiplier for computational budget scaling.
        """
        super().__init__(time_factor)
        self.tabu_tenure = tabu_tenure
        self.max_neighbors = max_neighbors
        self.seed = seed

    def _decode(self, solution: Solution, problem: ProblemInstance) -> List[Assignment]:
        """
        Transform solution representation into executable schedule.

        Computes feasible start times respecting precedence constraints
        and resource availability windows.
        """
        scheduled_finishes: Dict[int, int] = {}
        assignments: List[Assignment] = []
        team_available = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        todo = list(solution.task_order)

        progress = True
        while progress and todo:
            progress = False
            new_todo = []
            for task_id in todo:
                if task_id in scheduled_finishes:
                    continue

                task = problem.tasks[task_id]
                team_id = solution.team_assignment[task_id]

                # Verify all dependencies are satisfied
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

                # Compute earliest feasible start
                start_time = max(team_available[team_id], preds_complete_time)
                assignments.append(Assignment(task_id, team_id, start_time))
                finish_time = start_time + task.duration
                scheduled_finishes[task_id] = finish_time
                team_available[team_id] = finish_time
                progress = True
            todo = new_todo
        return assignments

    def _evaluate(
        self, solution: Solution, problem: ProblemInstance
    ) -> Tuple[int, int, int]:
        """
        Compute multi-objective fitness with memoization.

        Returns:
            Tuple of (-scheduled_count, makespan, total_cost) for
            lexicographic minimization.
        """
        if solution.fitness is not None:
            return solution.fitness

        assignments = self._decode(solution, problem)

        if not assignments:
            return (0, sys.maxsize, sys.maxsize)

        task_count = len(assignments)
        completion_time = 0
        total_cost = 0

        for a in assignments:
            task = problem.tasks[a.task_id]
            completion_time = max(completion_time, a.start_time + task.duration)
            total_cost += task.compatible_teams.get(a.team_id, 10**12)

        solution.fitness = (-task_count, completion_time, total_cost)
        return solution.fitness

    def _generate_initial_solution(
        self, problem: ProblemInstance, tasks_with_teams: List[int]
    ) -> Solution:
        """
        Construct initial solution via greedy dispatching rule.

        Iteratively selects the task-team pair that minimizes earliest
        start time, with cost as tiebreaker.
        """
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

        return Solution(task_order=task_order, team_assignment=team_assignment)

    def _get_neighbors(
        self,
        current: Solution,
        problem: ProblemInstance,
        tabu_list: Dict[Move, int],
        current_iter: int,
    ) -> List[Tuple[Solution, Move]]:
        """
        Generate candidate moves in the solution neighborhood.

        Neighborhood structure:
            - Pairwise task position exchanges
            - Single task resource reassignments

        Returns:
            List of (candidate_solution, associated_move) pairs.
        """
        neighbors = []
        task_order = current.task_order
        n = len(task_order)

        # Position exchange neighborhood
        swap_candidates = []
        for i in range(n):
            for j in range(i + 1, n):
                swap_candidates.append((i, j))

        # Limit neighborhood size via random sampling
        if len(swap_candidates) > self.max_neighbors // 2:
            swap_candidates = random.sample(swap_candidates, self.max_neighbors // 2)

        for i, j in swap_candidates:
            new_order = list(task_order)
            new_order[i], new_order[j] = new_order[j], new_order[i]

            move = Move("swap", task_order[i], task_order[j])
            neighbor = Solution(
                task_order=new_order, team_assignment=dict(current.team_assignment)
            )
            neighbors.append((neighbor, move))

        # Resource reassignment neighborhood
        team_candidates = []
        for tid in current.team_assignment:
            task = problem.tasks[tid]
            current_team = current.team_assignment[tid]
            for new_team in task.compatible_teams:
                if new_team != current_team:
                    team_candidates.append((tid, new_team))

        # Bound exploration via stochastic selection
        if len(team_candidates) > self.max_neighbors // 2:
            team_candidates = random.sample(team_candidates, self.max_neighbors // 2)

        for tid, new_team in team_candidates:
            new_assignment = dict(current.team_assignment)
            new_assignment[tid] = new_team

            move = Move("team", tid, new_team)
            neighbor = Solution(
                task_order=list(current.task_order), team_assignment=new_assignment
            )
            neighbors.append((neighbor, move))

        return neighbors

    def _is_tabu(
        self, move: Move, tabu_list: Dict[Move, int], current_iter: int
    ) -> bool:
        """Determine if the given move is currently forbidden."""
        if move not in tabu_list:
            return False
        return tabu_list[move] > current_iter

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
            # Initialize with constructive heuristic
            current = self._generate_initial_solution(problem, tasks_with_teams)
            current_score = self._evaluate(current, problem)

            best = current
            best_score = current_score

            # Short-term memory: maps moves to expiration iteration
            tabu_list: Dict[Move, int] = {}
            iteration = 0

            while not budget.is_expired():
                iteration += 1

                # Explore neighborhood
                neighbors = self._get_neighbors(current, problem, tabu_list, iteration)

                if not neighbors:
                    break

                # Select best admissible move (aspiration overrides tabu status)
                best_neighbor = None
                best_neighbor_score = (sys.maxsize, sys.maxsize, sys.maxsize)
                best_move = None

                for neighbor, move in neighbors:
                    if budget.is_expired():
                        break

                    score = self._evaluate(neighbor, problem)
                    is_tabu = self._is_tabu(move, tabu_list, iteration)

                    # Aspiration: override tabu if global improvement achieved
                    if is_tabu and score >= best_score:
                        continue

                    if score < best_neighbor_score:
                        best_neighbor = neighbor
                        best_neighbor_score = score
                        best_move = move

                if best_neighbor is None:
                    # Diversification: random restart on stagnation
                    task_order = list(tasks_with_teams)
                    random.shuffle(task_order)
                    team_assignment = {}
                    for tid in tasks_with_teams:
                        task = problem.tasks[tid]
                        team_assignment[tid] = random.choice(
                            list(task.compatible_teams.keys())
                        )
                    current = Solution(
                        task_order=task_order, team_assignment=team_assignment
                    )
                    current_score = self._evaluate(current, problem)
                    continue

                # Transition to selected neighbor
                current = best_neighbor
                current_score = best_neighbor_score

                # Record move in short-term memory
                if best_move:
                    tabu_list[best_move] = iteration + self.tabu_tenure

                    # Forbid inverse operation to prevent immediate reversal
                    if best_move.move_type == "swap":
                        reverse = Move("swap", best_move.task_id_2, best_move.task_id_1)
                        tabu_list[reverse] = iteration + self.tabu_tenure

                # Track incumbent solution
                if current_score < best_score:
                    best = current
                    best_score = current_score

                # Periodic memory maintenance
                if iteration % 100 == 0:
                    tabu_list = {
                        m: exp for m, exp in tabu_list.items() if exp > iteration
                    }

            return Schedule(assignments=self._decode(best, problem))
