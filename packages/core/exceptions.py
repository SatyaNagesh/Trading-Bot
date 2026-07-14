class QuantLabError(Exception):
    """Base exception for all QuantLab AI errors."""


class ConfigurationError(QuantLabError):
    """Raised when configuration is invalid or missing."""


class DataError(QuantLabError):
    """Raised when data operations fail."""


class DataQualityError(DataError):
    """Raised when data fails quality checks."""


class DataNotFoundError(DataError):
    """Raised when requested data is not available."""


class StrategyError(QuantLabError):
    """Raised when strategy operations fail."""


class StrategyValidationError(StrategyError):
    """Raised when strategy definition fails validation."""


class BacktestError(QuantLabError):
    """Raised when backtesting fails."""


class RiskError(QuantLabError):
    """Raised when risk limits are breached or risk computation fails."""


class RiskLimitBreach(RiskError):
    """Raised when a hard risk limit is violated."""


class ExecutionError(QuantLabError):
    """Raised when order execution fails."""


class BrokerError(ExecutionError):
    """Raised when broker communication fails."""


class OrderRejectedError(ExecutionError):
    """Raised when an order is rejected."""


class DatabaseError(QuantLabError):
    """Raised when database operations fail."""


class AIAgentError(QuantLabError):
    """Raised when AI agent operations fail."""


class ConstitutionalViolation(QuantLabError):
    """Raised when an action violates the 12 Laws."""


class EngineUnavailable(QuantLabError):
    """Raised when a dependent engine is not available."""
