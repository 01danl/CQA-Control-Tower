"""Signed dataset URLs and authorization headers must not reach transport logs."""

import logging


class _NoTransportDetails(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return False


def silence_transport_logs() -> None:
    for name in (
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
        "httpcore.connection_pool",
    ):
        logger = logging.getLogger(name)
        if not any(isinstance(f, _NoTransportDetails) for f in logger.filters):
            logger.addFilter(_NoTransportDetails())
