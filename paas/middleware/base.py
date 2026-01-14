from abc import ABC, abstractmethod
from typing import Protocol, List, Optional

from paas.models import ProblemInstance, Schedule
from paas.time_budget import TimeBudget


class Runnable(Protocol):
    def run(self, problem: ProblemInstance) -> Schedule: ...


class Solver(ABC):
    """
    Abstract solver class.
    """

    def __init__(self, time_factor: float = 1.0):
        self.time_factor = time_factor
        self.time_limit: float = float("inf")

    @abstractmethod
    def run(self, problem: ProblemInstance) -> Schedule:
        """
        Solve the problem and return a schedule.
        """
        pass


class Middleware(ABC):
    """
    Abstract middleware class.
    """

    def __init__(self, time_factor: float = 1.0):
        self.time_factor = time_factor
        self.time_limit: float = float("inf")

    @abstractmethod
    def run(self, problem: ProblemInstance, next_runnable: Runnable) -> Schedule:
        """
        Process the problem and return a schedule by optionally calling next_runnable.
        """
        pass


class MapProblem(Middleware):
    """
    Middleware specialized for transforming the problem instance
    before passing it to the next handler.
    """

    def run(self, problem: ProblemInstance, next_runnable: Runnable) -> Schedule:
        new_problem = self.map_problem(problem)
        return next_runnable.run(new_problem)

    @abstractmethod
    def map_problem(self, problem: ProblemInstance) -> ProblemInstance:
        """
        Transform the problem instance.
        """
        pass


class MapResult(Middleware):
    """
    Middleware specialized for refining the result (schedule)
    returned by the next handler.
    """

    def run(self, problem: ProblemInstance, next_runnable: Runnable) -> Schedule:
        result = next_runnable.run(problem)
        return self.map_result(problem, result)

    @abstractmethod
    def map_result(self, problem: ProblemInstance, result: Schedule) -> Schedule:
        """
        Refine the result.
        """
        pass


class _WrappedRunnable:
    def __init__(self, middleware: Middleware, next_runnable: Runnable):
        self.middleware = middleware
        self.next_runnable = next_runnable

    def run(self, problem: ProblemInstance) -> Schedule:
        return self.middleware.run(problem, self.next_runnable)


class Pipeline(Runnable):
    """
    Helper to chain multiple middlewares and a final solver.
    """

    def __init__(
        self,
        middlewares: List[Middleware],
        solver: Solver,
        total_budget: Optional[TimeBudget] = None,
    ):
        self.middlewares = middlewares
        self.solver = solver
        self.total_budget = total_budget

    def run(self, problem: ProblemInstance) -> Schedule:
        if self.total_budget:
            # Calculate total time factor
            solver_factor = self.solver.time_factor
            total_factor = sum(m.time_factor for m in self.middlewares) + solver_factor

            total_seconds = self.total_budget.duration_seconds

            # Assign budgets
            if total_factor > 0:
                for m in self.middlewares:
                    m.time_limit = (m.time_factor / total_factor) * total_seconds

                self.solver.time_limit = (solver_factor / total_factor) * total_seconds

        pipeline = self.solver
        for m in reversed(self.middlewares):
            pipeline = self._wrap(m, pipeline)
        return pipeline.run(problem)

    def _wrap(self, m: Middleware, next_runnable: Runnable) -> Runnable:
        return _WrappedRunnable(m, next_runnable)
