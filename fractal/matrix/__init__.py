import logging
import os
import re
from getpass import getpass
from typing import Optional, Tuple

logger = logging.getLogger(__file__)


class WellKnownNotFoundException(Exception):
    def __init__(self):
        super().__init__("Your Matrix server's .well-known/matrix/client was not found.")


class UnknownDiscoveryInfoException(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Unknown Error: {reason}")


class InvalidMatrixIdException(Exception):
    pass


def prompt_matrix_password(matrix_id: str) -> str:
    """
    Prompts for Matrix password.

    Args:
        matrix_id: Matrix ID to prompt for

    TODO: This should instead direct to a homeserver login page.
    """
    print(f"Login with Matrix ID ({matrix_id}) to continue")
    try:
        password = getpass(f"{matrix_id}'s password: ")
        return password
    except (KeyboardInterrupt, EOFError):
        # newline after ^C
        print()
        exit(1)


def parse_matrix_id(matrix_id: str) -> Tuple[str, str]:
    """Parse local part and homeserver from MatrixID"""
    pattern = re.compile(r"^@([^:]+):([^:]+)$")
    match = pattern.match(matrix_id)
    if not match:
        raise InvalidMatrixIdException(f"{matrix_id} is not a valid Matrix ID.")
    user_localpart = match.group(1)
    homeserver = match.group(2)
    return (user_localpart, homeserver)


async def get_homeserver_for_matrix_id(matrix_id: str):
    """Lookup the homeserver url associated with a Matrix ID"""
    # FIXME: just because matrix_id has localhost, doesn't necessarily mean
    # that the homeserver is running on localhost. Could be synapse:8008, etc.
    if "localhost" in matrix_id:
        return "http://localhost:8008"
    _, homeserver_host = parse_matrix_id(matrix_id)
    homeserver_url = f"https://{homeserver_host}"
    async with MatrixClient(homeserver_url) as client:
        res = await client.discovery_info()
    if not res.transport_response.ok:  # type: ignore
        if res.transport_response.reason == "Not Found":  # type: ignore
            raise WellKnownNotFoundException()  # type: ignore
        raise UnknownDiscoveryInfoException(f"Failed to get homeserver for MatrixID: {res.transport_response.reason}")  # type: ignore
    return res.homeserver_url  # type: ignore


class MatrixClient:
    """
    Helper decorator and context manager for use with code
    that communicates with Matrix via matrix-nio's AsyncClient.

    Args:
        homeserver_url: homeserver URL to set on the nio AsyncClient
            defaults to MATRIX_HOMESERVER_URL environment variable
        access_token: Access token to set on the nio AsyncClient
            defaults to MATRIX_ACCESS_TOKEN environment variable
        max_timeouts: Number of retries for failed requests
            defaults to 2

    @MatrixClient()
    async def example(client: FractalAsyncClient):
        await client.discovery_info()

        or

    async with MatrixClient("http://localhost:8008") as client:
        await client.discovery_info()
    """

    def __init__(
        self,
        homeserver_url: Optional[str] = None,
        access_token: str = os.environ.get("HS_ACCESS_TOKEN", ""),
        room_id: Optional[str] = None,
        max_timeouts: int = 0,
    ):
        from fractal.matrix.async_client import FractalAsyncClient

        try:
            self.homeserver_url = homeserver_url or os.environ["MATRIX_HOMESERVER_URL"]
            self.client = FractalAsyncClient(
                self.homeserver_url, access_token, room_id=room_id, max_timeouts=max_timeouts
            )
        except KeyError as e:
            if e.args[0] == "MATRIX_HOMESERVER_URL":
                raise KeyError(
                    "Environment variable MATRIX_HOMESERVER_URL must be set if\
 not passed explicitly to the MatrixClient context manager decorator."
                ) from e

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            async with self as client:
                return await func(*args, client, **kwargs)

        return wrapper

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.close()
