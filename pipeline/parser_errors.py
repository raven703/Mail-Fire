"""Secret-free parser failure taxonomy. Never include URLs or response bodies."""


class ParserError(RuntimeError):
    def __init__(self, operation, service, reason, status=None, retry_after=0):
        self.operation, self.service, self.reason = operation, service, reason
        self.status, self.retry_after = status, retry_after
        super().__init__(f"parser service={service} operation={operation} status={status or 0} reason={reason}")


class ParserUnavailable(ParserError):
    """Dependency is temporarily unavailable; not a failed processing attempt."""


class ParserRejected(ParserError):
    """Non-retryable input or protocol error."""