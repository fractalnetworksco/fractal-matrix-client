from typing import Optional


class GetLatestSyncTokenError(Exception):
    def __init__(self, message: Optional[str] = None) -> None:
        if message:
            super().__init__(f"Failed to get latest sync token: {message}")
        else:
            super().__init__("Failed to get latest sync token")
