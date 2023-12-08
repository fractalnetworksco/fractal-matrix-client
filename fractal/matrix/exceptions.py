from typing import Optional


class GetLatestSyncTokenError(Exception):
    def __init__(self, message: Optional[str] = None) -> None:
        if message:
            super().__init__(f"Failed to get latest sync token: {message}")
        else:
            super().__init__("Failed to get latest sync token")


class WellKnownNotFoundException(Exception):
    def __init__(self):
        super().__init__("Your Matrix server's .well-known/matrix/client was not found.")


class UnknownDiscoveryInfoException(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Unknown Error: {reason}")


class InvalidMatrixIdException(Exception):
    pass
