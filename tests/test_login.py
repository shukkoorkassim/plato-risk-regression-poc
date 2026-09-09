"""Regression tests for the LOGIN component (offline SwagLabs model)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from swaglabs import login, LoginError


def test_standard_user_logs_in():
    assert login("standard_user", "secret_sauce") == "session-standard_user"


def test_wrong_password_rejected():
    with pytest.raises(LoginError):
        login("standard_user", "wrong")


def test_locked_out_user_blocked():
    with pytest.raises(LoginError) as e:
        login("locked_out_user", "secret_sauce")
    assert "locked out" in str(e.value).lower()
