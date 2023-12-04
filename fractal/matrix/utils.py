import os
import re
from getpass import getpass
from os import makedirs
from typing import Any, Dict, Tuple

import appdirs
import yaml

data_dir = appdirs.user_data_dir("fractal")


class InvalidMatrixIdException(Exception):
    pass


def write_user_data(data: Dict[str, Any], filename: str) -> None:
    """
    Write data to yaml file <filename> in user's appdir (ie ~/.local/share/fractal)
    """
    makedirs(data_dir, exist_ok=True)

    try:
        data_to_write = yaml.dump(data)
    except yaml.YAMLError as error:
        raise error

    user_data = os.path.join(data_dir, filename)
    with open(user_data, "w") as file:
        file.write(data_to_write)


def read_user_data(filename: str) -> Tuple[Dict[str, Any], str]:
    """
    Reads data from <filename> in user's appdir (ie ~/.local/share/fractal)

    TODO: Support multiple file types. Right now this only supports yaml files.

    Returns:
        (user_data, data_file_path): Data in file (as dict), path to file (str).
    """
    data_file_path = os.path.join(data_dir, filename)

    try:
        with open(data_file_path, "r") as file:
            user_data = file.read()
    except FileNotFoundError as error:
        raise error

    try:
        user_data = yaml.safe_load(user_data)
    except yaml.YAMLError as error:
        raise error

    return user_data, data_file_path


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
