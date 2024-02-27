from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fractal.matrix import utils
from fractal.matrix.exceptions import InvalidMatrixIdException


async def test_prompt_matrix_password_if_homeserver_url(capsys):
    matrix_id = "test_matrix_id"
    homeserver_url = "homeserver_url"
    sample_password = "sample_password"
    with patch("fractal.matrix.utils.getpass", new=MagicMock(return_value=sample_password)):
        utils.prompt_matrix_password(matrix_id=matrix_id, homeserver_url=homeserver_url)
        text = capsys.readouterr()
    assert (
        f"Login with Matrix ID ({matrix_id}) to sign in to {homeserver_url}" == text.out.strip()
    )


async def test_prompt_matrix_password_if_no_homeserver_url(capsys):
    matrix_id = "test_matrix_id"
    sample_password = "sample_password"
    with patch("fractal.matrix.utils.getpass", new=MagicMock(return_value=sample_password)):
        utils.prompt_matrix_password(matrix_id=matrix_id)
        text = capsys.readouterr()
    assert f"Login with Matrix ID ({matrix_id}) to continue" == text.out.strip()


async def test_prompt_matrix_password_no_interrupt():
    matrix_id = "test_matrix_id"
    sample_password = "sample_password"
    with patch("fractal.matrix.utils.getpass", new=MagicMock(return_value=sample_password)):
        password = utils.prompt_matrix_password(matrix_id)
    assert password == sample_password


async def test_prompt_matrix_password_keyboard_interrupt():
    matrix_id = "test_matrix_id"
    with pytest.raises(SystemExit) as e:
        with patch("fractal.matrix.utils.getpass", new=MagicMock(side_effect=KeyboardInterrupt)):
            utils.prompt_matrix_password(matrix_id)
    assert e.type == SystemExit


async def test_parse_matrix_id_group_returns():
    matrix_id = "test_matrix_id"
    sample_localpart = "test_localpart"
    sample_homeserver = "test_homeserver"
    compiled_pattern_mock = MagicMock()
    match_mock = MagicMock()
    compiled_pattern_mock.match.return_value = match_mock
    with patch("re.compile", return_value=compiled_pattern_mock):
        with patch.object(
            match_mock, "group", return_value=(sample_localpart, sample_homeserver)
        ):
            localpart, homeserver = utils.parse_matrix_id(matrix_id)
    assert localpart[0] == sample_localpart
    assert homeserver[1] == sample_homeserver


async def test_parse_matrix_id_invalidmatrixidexception():
    matrix_id = "test_matrix_id"
    compiled_pattern_mock = MagicMock()
    compiled_pattern_mock.match.return_value = None
    with patch("re.compile", return_value=compiled_pattern_mock):
        with pytest.raises(InvalidMatrixIdException) as e:
            utils.parse_matrix_id(matrix_id)
        assert f"{matrix_id} is not a valid Matrix ID." in str(e.value)
