"""Domain exceptions for context construction."""


class ContextEngineError(Exception):
    """Base error for context engine failures."""


class InvalidRequestError(ContextEngineError):
    """The request is malformed or internally inconsistent."""


class AmbiguousRequestError(ContextEngineError):
    """The request does not identify exactly one move to explain."""


class AnalysisError(ContextEngineError):
    """Engine or analysis evidence could not be produced."""
