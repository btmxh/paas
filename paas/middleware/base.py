from sys import stderr
from paas.checker import validate_schedule
from abc import ABC, abstractmethod
from typing import Protocol, List, Optional

from paas.models import ProblemInstance, Schedule
from paas.time_budget import TimeBudget


class Runnable(Protocol):
    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule: ...


class Solver(ABC):
    """
    Abstract solver class.
    """

    def __init__(self, time_factor: float = 1.0):
        self.time_factor = time_factor

    @abstractmethod
    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        """
        Solve the problem and return a schedule.
        """
        pass


class Middleware(ABC):
    """
    Abstract middleware class.
    """

    def __init__(self, time_factor: float = 0.0):
        self.time_factor = time_factor

    @abstractmethod
    def run(
        self,
        problem: ProblemInstance,
        next_runnable: Runnable,
        time_limit: float = float("inf"),
    ) -> Schedule:
        """
        Process the problem and return a schedule by optionally calling next_runnable.
        """
        pass


class MapProblem(Middleware):
    """
    Middleware specialized for transforming the problem instance
    before passing it to the next handler.
    """

    def run(
        self,
        problem: ProblemInstance,
        next_runnable: Runnable,
        time_limit: float = float("inf"),
    ) -> Schedule:
        new_problem = self.map_problem(problem, time_limit=time_limit)
        return next_runnable.run(new_problem, time_limit=time_limit)

    @abstractmethod
    def map_problem(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> ProblemInstance:
        """
        Transform the problem instance.
        """
        pass


class MapResult(Middleware):
    """
    Middleware specialized for refining the result (schedule)
    returned by the next handler.
    """

    def run(
        self,
        problem: ProblemInstance,
        next_runnable: Runnable,
        time_limit: float = float("inf"),
    ) -> Schedule:
        result = next_runnable.run(problem, time_limit=time_limit)
        return self.map_result(problem, result, time_limit=time_limit)

    @abstractmethod
    def map_result(
        self,
        problem: ProblemInstance,
        result: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        """
        Refine the result.
        """
        pass


class _BudgetedRunnable:
    def __init__(self, runnable: Runnable, budget: float):
        self.runnable = runnable
        self.budget = budget

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        # Ignore passed time_limit, strictly enforce assigned budget
        return self.runnable.run(problem, time_limit=self.budget)


class _BudgetedMiddlewareRunnable:
    def __init__(self, middleware: Middleware, next_runnable: Runnable, budget: float):
        self.middleware = middleware
        self.next_runnable = next_runnable
        self.budget = budget

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        # Inject budget
        return self.middleware.run(problem, self.next_runnable, time_limit=self.budget)


class _WrappedRunnable:
    def __init__(self, middleware: Middleware, next_runnable: Runnable):
        self.middleware = middleware
        self.next_runnable = next_runnable

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        # Pass through
        return self.middleware.run(problem, self.next_runnable, time_limit=time_limit)


class Pipeline(Runnable):
    """
    Helper to chain multiple middlewares and a final solver.
    """

    def __init__(
        self,
        middlewares: List[Middleware],
        solver: Solver,
        total_budget: Optional[TimeBudget] = None,
        check: bool = True,
    ):
        self.middlewares = middlewares
        self.solver = solver
        self.total_budget = total_budget
        self.check = check

    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        # If total_budget is set, it overrides the time_limit param for calculation purposes,
        # or we treat time_limit param as the total budget if total_budget is not set?
        # The prompt examples used Pipeline(..., total_budget=TimeBudget).

        pipeline = self.solver

        use_budget = False
        if self.total_budget:
            total_seconds = self.total_budget.duration_seconds
            use_budget = True
        elif time_limit != float("inf"):
            total_seconds = time_limit
            use_budget = True

        if use_budget:
            solver_factor = self.solver.time_factor
            total_factor = sum(m.time_factor for m in self.middlewares) + solver_factor

            # Wrap solver with budget
            solver_budget = (
                (solver_factor / total_factor) * total_seconds
                if total_factor > 0
                else 0
            )
            pipeline = _BudgetedRunnable(self.solver, solver_budget)

            # Wrap middlewares
            for m in reversed(self.middlewares):
                m_budget = (
                    (m.time_factor / total_factor) * total_seconds
                    if total_factor > 0
                    else 0
                )
                pipeline = _BudgetedMiddlewareRunnable(m, pipeline, m_budget)
        else:
            # No budget logic, just standard wrapping
            for m in reversed(self.middlewares):
                pipeline = _WrappedRunnable(m, pipeline)

        schedule = pipeline.run(problem)
        if self.check:
            result = validate_schedule(problem, schedule)
            if not result.is_valid:
                print("Warning: The produced schedule is invalid:", file=stderr)
                for error in result.errors:
                    print(f"- {error.message}", file=stderr)
        return schedule
