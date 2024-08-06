import json
import secrets
from typing import Tuple

import requests
from asgiref.sync import async_to_sync


class MatrixAdminClient:
    def __init__(self, *, homeserver_url: str, admin_access_token: str):
        self.homeserver_url = homeserver_url
        self.admin_access_token = admin_access_token

    def do_request(self, method, endpoint, body=None) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {self.admin_access_token}",
            "Content-Type": "application/json",
        }
        response = requests.request(
            method, f"{self.homeserver_url}{endpoint}", headers=headers, data=json.dumps(body)
        )

        # Check for successful response
        response.raise_for_status()
        return response

    def check_user_availability(self, user_id):
        """
        Method to check if a user_id is available
        """
        localpart = user_id.split(":")[0][1:]
        try:
            self.do_request("GET", f"/_synapse/admin/v1/username_available?username={localpart}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                return False
            else:
                raise e
        return True

    async def create_or_modify_user(
        self,
        user_id,
        *,
        password=None,
        logout_devices=True,
        displayname=None,
        avatar_url=None,
        threepids=None,
        external_ids=None,
        admin=False,
        deactivated=False,
        user_type=None,
        locked=False,
    ) -> None:
        """
        Create or modify a user account using the Synapse Admin API.

        Args:
        base_url (str): The base URL of your Synapse server (e.g., "https://matrix.example.com")
        access_token (str): The access token of an admin user
        user_id (str): The fully-qualified user ID (e.g., "@user:server.com")
        password (str, optional): User's password. Defaults to None.
        logout_devices (bool, optional): Whether to log out devices when changing password. Defaults to True.
        displayname (str, optional): User's display name. Defaults to None.
        avatar_url (str, optional): MXC URI of user's avatar. Defaults to None.
        threepids (list, optional): List of third-party IDs (email, phone). Defaults to None.
        external_ids (list, optional): List of external identity provider IDs. Defaults to None.
        admin (bool, optional): Whether the user is an admin. Defaults to False.
        deactivated (bool, optional): Whether the account is deactivated. Defaults to False.
        user_type (str or None, optional): Type of user account. Defaults to None.
        locked (bool, optional): Whether the account is locked. Defaults to False.

        Returns:
        dict: The JSON response from the server
        """

        if "@" not in user_id:
            raise ValueError("User ID must be fully-qualified (e.g., '@user:server.com')")
        elif ":" not in user_id:
            raise ValueError("User ID must be fully-qualified (e.g., '@user:server.com')")

        if not self.check_user_availability(user_id):
            raise ValueError(f"User ID '{user_id}' is not available")

        endpoint = f"/_synapse/admin/v2/users/{user_id}"

        if not password:
            password = secrets.token_hex(16)

        # Prepare the request body
        body = {
            "password": password,
            "logout_devices": logout_devices,
            "displayname": displayname,
            "avatar_url": avatar_url,
            "threepids": threepids,
            "external_ids": external_ids,
            "admin": admin,
            "deactivated": deactivated,
            "user_type": user_type,
            "locked": locked,
        }

        # Remove None values from the body
        body = {k: v for k, v in body.items() if v is not None}

        # Make the API request
        # TODO make me async
        self.do_request("PUT", endpoint, body)

    async def alogin(self, user_id, password):
        from fractal.matrix import MatrixClient

        async with MatrixClient(self.homeserver_url) as client:
            client.user = user_id
            result = await client.login(password)
            return result.user_id, result.access_token

    def login(self, user_id, password):
        return async_to_sync(self.alogin)(user_id, password)
