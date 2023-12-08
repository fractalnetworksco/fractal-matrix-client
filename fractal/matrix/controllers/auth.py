import os
from sys import exit
from typing import Optional, Tuple

from asgiref.sync import async_to_sync
from fractal.cli import cli_method
from fractal.cli.utils import read_user_data, write_user_data
from fractal.matrix import MatrixClient, get_homeserver_for_matrix_id
from fractal.matrix.utils import prompt_matrix_password
from nio import LoginError


class MatrixLoginError(Exception):
    pass


class AuthController:
    PLUGIN_NAME = "auth"
    TOKEN_FILE = "matrix.creds.yaml"

    @cli_method
    def login(self, matrix_id: str, homeserver_url: Optional[str] = None):
        """
        Login to a Matrix homeserver.
        ---
        Args:
            matrix_id: Matrix ID of user to login as
            homeserver_url: Homeserver to login to

        """

        homeserver_url, access_token = async_to_sync(self._login_with_password)(
            matrix_id, homeserver_url=homeserver_url
        )

        # save access token to token file
        write_user_data(
            {
                "access_token": access_token,
                "homeserver_url": homeserver_url,
                "matrix_id": matrix_id,
            },
            self.TOKEN_FILE,
        )

        print(f"Successfully logged in as {matrix_id}")

    login.clicz_aliases = ["login"]

    @cli_method
    def logout(self):
        """
        Logout of Matrix
        ---
        Args:
        """
        try:
            data, path = read_user_data(self.TOKEN_FILE)
            access_token = data["access_token"]
            homeserver_url = data["homeserver_url"]
        except KeyError:
            raise
        except FileNotFoundError:
            print("You are not logged in.")
            return

        async def _logout():
            async with MatrixClient(homeserver_url, access_token) as client:
                await client.logout()

        if os.path.exists(path):
            os.remove(path)
            async_to_sync(_logout)()
            print("Successfully logged out. Have a nice day.")

    logout.clicz_aliases = ["logout"]

    async def _login_with_password(
        self, matrix_id: str, password: Optional[str] = None, homeserver_url: Optional[str] = None
    ) -> Tuple[str, str]:
        if not homeserver_url:
            homeserver_url = await get_homeserver_for_matrix_id(matrix_id)
        if not password:
            password = prompt_matrix_password(matrix_id)
        async with MatrixClient(homeserver_url) as client:
            client.user = matrix_id
            res = await client.login(password)
            if isinstance(res, LoginError):
                raise MatrixLoginError(res.message)
        return homeserver_url, res.access_token

    @cli_method
    def show(self, key: str):
        """

        ---
        Args:
            key: Key to show. Such as 'access_token' or 'homeserver_url'.
        """
        try:
            data, _ = read_user_data(self.TOKEN_FILE)
        except KeyError:
            raise

        match key:
            case "access_token":
                print(data["access_token"])
            case "homeserver_url":
                print(data["homeserver_url"])
            case "matrix_id":
                print(data["matrix_id"])


Controller = AuthController
