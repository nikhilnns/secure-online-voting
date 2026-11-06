"""Unit tests: input validation functions."""
import pytest

from backend.middleware.validation import (clean_text, validate_email, validate_name,
                                           validate_password, validate_voter_id)
from backend.utils.errors import ServiceError


@pytest.mark.parametrize("email", ["user@", "plainaddress", "a@b", "@x.com", "", None, 42])
def test_invalid_email_returns_error(email):
    """TC-01: invalid e-mail formats are rejected."""
    assert validate_email(email) is not None


def test_valid_email_passes():
    assert validate_email("pratyush@college.edu") is None


@pytest.mark.parametrize("password,fragment", [
    ("short1A", "at least 8"),
    ("alllowercase1", "upper and lower"),
    ("NoDigitsHere", "digit"),
    ("", "required"),
])
def test_weak_passwords_rejected(password, fragment):
    """TC-02: password policy enforcement."""
    assert fragment in validate_password(password)


def test_strong_password_accepted():
    assert validate_password("Secure@2026") is None


def test_voter_id_rules():
    assert validate_voter_id("1BY23IS156") is None
    assert validate_voter_id("AB") is not None
    assert validate_voter_id("1BY23 IS156") is not None
    assert validate_voter_id("<script>") is not None


def test_name_rules():
    assert validate_name("Pratyush Kesari A") is None
    assert validate_name("1234") is not None
    assert validate_name("<b>x</b>") is not None


def test_clean_text_trims_and_limits():
    assert clean_text("  hello  ", 10, "Title") == "hello"
    with pytest.raises(ServiceError):
        clean_text("x" * 11, 10, "Title")
    with pytest.raises(ServiceError):
        clean_text("   ", 10, "Title")
    assert clean_text(None, 10, "Desc", required=False) == ""
