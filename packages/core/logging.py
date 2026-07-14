import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.dev import ConsoleRenderer


def setup_logging(env: str = "development") -> None:
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if env == "production":
        processors = shared_processors + [JSONRenderer()]
    else:
        processors = shared_processors + [
            ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "quantlab") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
