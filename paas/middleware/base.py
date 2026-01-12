from abc import ABC, abstractmethod
from typing import Protocol, List

from paas.models import ProblemInstance, Schedule


class Runnable(Protocol):
    def run(self, problem: ProblemInstance) -> Schedule: ...


class Middleware(ABC):
    """
    Abstract middleware class.
    """

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
        return self.map_result(result)

    @abstractmethod
    def map_result(self, result: Schedule) -> Schedule:
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

    def __init__(self, middlewares: List[Middleware], solver: Runnable):
        self.middlewares = middlewares
        self.solver = solver

    def run(self, problem: ProblemInstance) -> Schedule:
        pipeline = self.solver
        for m in reversed(self.middlewares):
            pipeline = self._wrap(m, pipeline)
        return pipeline.run(problem)

    def _wrap(self, m: Middleware, next_runnable: Runnable) -> Runnable:
        return _WrappedRunnable(m, next_runnable)
