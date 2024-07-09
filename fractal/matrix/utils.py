import re
from getpass import getpass
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple
from uuid import uuid4

from fractal.matrix.exceptions import InvalidMatrixIdException
from nio import (
    BadEventType,
    Event,
    MessageDirection,
    RoomMessagesError,
    SyncError,
    Timeline,
)

if TYPE_CHECKING:
    from fractal.matrix.async_client import FractalAsyncClient


def invite_filter() -> dict[str, Any]:
    return {
        "presence": {"limit": 0, "types": []},
        "account_data": {"limit": 0, "types": []},
        "room": {
            "state": {"types": ["m.room.join_rules"], "not_types": ["m.room.member"], "limit": 0},
            "timeline": {"types": [], "limit": 0},
            "account_data": {"limit": 0, "types": []},
            "ephemeral": {"limit": 0, "types": []},
        },
        "request_id": str(uuid4()),
    }


def prompt_matrix_password(matrix_id: str, homeserver_url: Optional[str] = None) -> str:
    """
    Prompts for Matrix password.

    Args:
        matrix_id: Matrix ID to prompt for

    TODO: This should instead direct to a homeserver login page.
    """
    if homeserver_url:
        print(f"Login with Matrix ID ({matrix_id}) to sign in to {homeserver_url}")
    else:
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


def create_filter(
    room_id: Optional[str] = None,
    types: list = [],
    not_types: list = [],
    limit: Optional[int] = None,
    not_senders: list = [],
    room_event_filter: bool = False,
) -> Dict[str, Any]:
    """
    Create a filter for a room and/or specific message types.

    Returns:
        filter dict
    """
    message_filter = {
        "presence": {"limit": 0, "types": []},
        "account_data": {"limit": 0, "types": []},
        "room": {
            "state": {"types": [], "limit": 0},
            "timeline": {
                "types": [*types],
                "not_types": [*not_types],
                "not_senders": [*not_senders],
            },
        },
        "request_id": str(uuid4()),
    }
    if room_id is not None:
        message_filter["room"]["rooms"] = [room_id]

    if limit is not None:
        message_filter["room"]["timeline"]["limit"] = limit

    if room_event_filter:
        room_filter = message_filter["room"]["timeline"]
        room_filter["request_id"] = message_filter["request_id"]
        return room_filter

    return message_filter


def create_state_filter(
    room_id: Optional[str] = None,
    types: list = [],
    not_types: list = [],
    limit: Optional[int] = None,
    not_senders: list = [],
) -> Dict[str, Any]:
    """
    Create a filter for a room and/or specific message types.

    Returns:
        filter dict
    """
    message_filter = {
        "presence": {"limit": 0, "types": []},
        "account_data": {"limit": 0, "types": []},
        "room": {
            "state": {
                "types": [*types],
                "not_types": [*not_types],
                "not_senders": [*not_senders],
            },
            "timeline": {"types": [], "limit": 0},
        },
        "request_id": str(uuid4()),
    }
    if room_id is not None:
        message_filter["room"]["rooms"] = [room_id]

    if limit is not None:
        message_filter["room"]["state"]["limit"] = limit

    return message_filter


def create_sync_filter(
    room_id: Optional[str] = None,
    types: list = [],
    not_types: list = [],
    limit: Optional[int] = None,
    not_senders: list = [],
):
    """
    Creates a filter that works with the sync endpoint.
    """
    return create_filter(
        room_id=room_id,
        types=types,
        not_types=not_types,
        limit=limit,
        not_senders=not_senders,
    )


def create_room_message_filter(
    room_id: str,
    types: list = [],
    not_types: list = [],
    limit: Optional[int] = None,
    not_senders: list = [],
):
    """
    Creates a filter that works with the room_messages endpoint.
    """
    return create_filter(
        room_id=room_id,
        types=types,
        not_types=not_types,
        limit=limit,
        not_senders=not_senders,
        room_event_filter=True,
    )


def get_content_only(event: BadEventType | Event):
    content = event.source["content"]
    content["sender"] = event.sender
    content["event_id"] = event.event_id
    return content


async def run_sync_filter(
    client: "FractalAsyncClient",
    filter: dict,
    timeout: int = 30000,
    since: Optional[str] = None,
    content_only: bool = True,
    state: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    Execute a filter with the provided client, optionally filter message body by kwargs
    attempts to deserialize json
    """
    if since is None:
        client.next_batch = None  # type:ignore

    res = await client.sync(timeout=timeout, sync_filter=filter, since=since)
    if isinstance(res, SyncError):
        raise Exception(res.message)

    rooms = list(res.rooms.join.keys())
    d = {}
    for room in rooms:
        if not state:
            if content_only:
                d[room] = [
                    get_content_only(event) for event in res.rooms.join[room].timeline.events
                ]
            else:
                d[room] = [event for event in res.rooms.join[room].timeline.events]
        else:
            if content_only:
                d[room] = [get_content_only(event) for event in res.rooms.join[room].state]
            else:
                d[room] = [event for event in res.rooms.join[room].state]

    return d


async def sync_room_timelines(
    client: "FractalAsyncClient",
    filter: dict,
    timeout: int = 30000,
    since: Optional[str] = None,
    **kwargs,
) -> Dict[str, Timeline]:
    """
    Execute a filter with the provided client.
    """
    if since is None:
        client.next_batch = None  # type:ignore

    res = await client.sync(timeout=timeout, sync_filter=filter, since=since)
    if isinstance(res, SyncError):
        raise Exception(res.message)

    rooms = list(res.rooms.join.keys())
    d = {}
    for room in rooms:
        d[room] = res.rooms.join[room].timeline

    return d


async def run_room_message_filter(
    client: "FractalAsyncClient",
    room_id: str,
    filter: dict,
    start: str = "",
    end: Optional[str] = None,
    content_only: bool = True,
    direction: MessageDirection = MessageDirection.front,
    limit: int = 100,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Execute a room message request with the provided client attempts to deserialize json
    """
    since = start

    if end is None and direction == MessageDirection.back:
        end = ""

    res = await client.room_messages(
        room_id,
        start=since,
        end=end,
        limit=limit,
        direction=direction,
        message_filter=filter,
    )
    if isinstance(res, RoomMessagesError):
        raise Exception(res.message)

    d = {}
    if res.chunk:
        if content_only:
            d[room_id] = [get_content_only(event) for event in res.chunk]
        else:
            d[room_id] = [event for event in res.chunk]

    if direction == MessageDirection.back:
        return d, res.start
    else:
        return d, res.end
