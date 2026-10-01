"""Authentication settings: what is required where, and that no value is ever echoed.

See specs/004-email-otp-auth/contracts/configuration.md and, for the teacher and student lists,
specs/005-roles-authorization/contracts/configuration.md. Every case passes an explicit `environ`
dict to `resolve_auth_settings`, never `os.environ`, so nothing depends on the shell running the
suite.
"""

import logging

import pytest

from app.core.config import (
    DEV_SECRET_KEY,
    AuthConfigError,
    AuthSettings,
    resolve_auth_settings,
)

WARNING_LOGGER = "uvicorn.error"

GOOD_KEY = "k" * 32
RENDER_OK = {
    "RENDER": "true",
    "EMAIL_BACKEND": "resend",
    "SECRET_KEY": GOOD_KEY,
    "ADMIN_EMAILS": "admin@example.com",
    "RESEND_API_KEY": "re_test_key",
    "EMAIL_FROM": "Student Competitions <login@example.org>",
}

C1 = "EMAIL_BACKEND must be one of console, memory, resend."
C2 = "EMAIL_BACKEND must be 'resend' when running on Render."
C3 = "SECRET_KEY is required when running on Render."
C4 = "SECRET_KEY must be at least 32 characters long."
C5 = "ADMIN_EMAILS must list at least one address when running on Render."
C7 = "RESEND_API_KEY is required for the resend email backend."
C8 = "EMAIL_FROM is required for the resend email backend and must be a valid sender address."
W1 = "SECRET_KEY is not set; using an insecure development key. Never do this in production."
W2 = "EMAIL_BACKEND is not set; login emails will be printed to this console."
W3 = "ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator."
W4 = "No role lists are set; nobody will be able to sign in."


def error_lines(environ: dict[str, str]) -> list[str]:
    with pytest.raises(AuthConfigError) as caught:
        resolve_auth_settings(environ)
    lines = str(caught.value).splitlines()
    assert lines[0] == "Invalid authentication configuration:"
    return [line.strip().removeprefix("- ") for line in lines[1:]]


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == WARNING_LOGGER and record.levelno == logging.WARNING
    ]


# ---------------------------------------------------------------------------------------------
# Defaults and parsing
# ---------------------------------------------------------------------------------------------


def test_nothing_set_locally_gives_the_development_defaults() -> None:
    settings = resolve_auth_settings({})
    assert settings.email_backend == "console"
    assert settings.secret_key == DEV_SECRET_KEY
    assert settings.admin_emails == ()
    assert settings.production is False
    assert settings.resend_api_key is None
    assert settings.email_from is None


def test_the_development_key_is_long_enough_and_labelled() -> None:
    assert len(DEV_SECRET_KEY) >= 32
    assert "insecure" in DEV_SECRET_KEY


def test_empty_strings_count_as_unset() -> None:
    settings = resolve_auth_settings(
        {
            "EMAIL_BACKEND": "",
            "SECRET_KEY": "",
            "ADMIN_EMAILS": "",
            "RESEND_API_KEY": "",
            "EMAIL_FROM": "",
            "RENDER": "",
        }
    )
    assert settings.email_backend == "console"
    assert settings.secret_key == DEV_SECRET_KEY
    assert settings.production is False


def test_admin_emails_are_trimmed_lowercased_deduplicated_and_sorted() -> None:
    settings = resolve_auth_settings({"ADMIN_EMAILS": " B@x.org, a@x.org ,A@X.ORG,"})
    assert settings.admin_emails == ("a@x.org", "b@x.org")


@pytest.mark.parametrize("name", ["TEACHER_EMAILS", "STUDENT_EMAILS"])
def test_the_new_lists_are_parsed_like_admin_emails(name: str) -> None:
    settings = resolve_auth_settings({name: " B@example.org, a@example.org ,A@EXAMPLE.ORG,"})
    field = name.lower()
    assert getattr(settings, field) == ("a@example.org", "b@example.org")


@pytest.mark.parametrize("value", [None, "", " , ,"])
def test_the_new_lists_may_be_unset_or_empty(value: str | None) -> None:
    """FR-037: nobody holds that role, and the start is allowed."""
    environ = {} if value is None else {"TEACHER_EMAILS": value, "STUDENT_EMAILS": value}
    settings = resolve_auth_settings(environ)
    assert settings.teacher_emails == ()
    assert settings.student_emails == ()


@pytest.mark.parametrize("backend", ["console", "memory"])
def test_local_backends_are_accepted(backend: str) -> None:
    assert resolve_auth_settings({"EMAIL_BACKEND": backend}).email_backend == backend


def test_a_complete_render_configuration_is_accepted() -> None:
    settings = resolve_auth_settings(RENDER_OK)
    assert settings.production is True
    assert settings.email_backend == "resend"
    assert settings.secret_key == GOOD_KEY
    assert settings.admin_emails == ("admin@example.com",)
    assert settings.resend_api_key == "re_test_key"
    assert settings.email_from == "Student Competitions <login@example.org>"


def test_auth_config_error_is_a_runtime_error() -> None:
    assert issubclass(AuthConfigError, RuntimeError)


# ---------------------------------------------------------------------------------------------
# Rules C1–C8
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("render", [False, True])
def test_c1_an_unknown_backend_is_refused_everywhere(render: bool) -> None:
    environ = {**RENDER_OK, "EMAIL_BACKEND": "smtp"} if render else {"EMAIL_BACKEND": "smtp"}
    assert C1 in error_lines(environ)


@pytest.mark.parametrize("backend", [None, "console", "memory"])
def test_c2_render_requires_the_resend_backend(backend: str | None) -> None:
    environ = dict(RENDER_OK)
    if backend is None:
        del environ["EMAIL_BACKEND"]
    else:
        environ["EMAIL_BACKEND"] = backend
    assert error_lines(environ) == [C2]


def test_c3_render_requires_a_secret_key() -> None:
    environ = {k: v for k, v in RENDER_OK.items() if k != "SECRET_KEY"}
    assert error_lines(environ) == [C3]


@pytest.mark.parametrize("render", [False, True])
def test_c4_a_short_secret_key_is_refused_everywhere(render: bool) -> None:
    base = dict(RENDER_OK) if render else {}
    assert error_lines({**base, "SECRET_KEY": "s" * 31}) == [C4]
    assert resolve_auth_settings({**base, "SECRET_KEY": "s" * 32}).secret_key == "s" * 32


@pytest.mark.parametrize("value", [None, "", " , ,"])
def test_c5_render_requires_at_least_one_admin(value: str | None) -> None:
    environ = dict(RENDER_OK)
    if value is None:
        del environ["ADMIN_EMAILS"]
    else:
        environ["ADMIN_EMAILS"] = value
    assert error_lines(environ) == [C5]


@pytest.mark.parametrize("render", [False, True])
def test_c6_malformed_admin_entries_are_reported_by_position(render: bool) -> None:
    base = dict(RENDER_OK) if render else {}
    # Positions count non-empty entries only: the blank between the commas is skipped.
    environ = {**base, "ADMIN_EMAILS": "ok@x.org, ,bad, also@x.org,@nope"}
    assert error_lines(environ) == [
        "ADMIN_EMAILS entry 2 is not a valid email address.",
        "ADMIN_EMAILS entry 4 is not a valid email address.",
    ]


def test_c7_resend_requires_an_api_key_locally_too() -> None:
    environ = {"EMAIL_BACKEND": "resend", "EMAIL_FROM": "login@example.org"}
    assert error_lines(environ) == [C7]


def test_c7_render_requires_an_api_key() -> None:
    environ = {k: v for k, v in RENDER_OK.items() if k != "RESEND_API_KEY"}
    assert error_lines(environ) == [C7]


@pytest.mark.parametrize("value", [None, "not-an-address", "Name <broken>"])
def test_c8_resend_requires_a_valid_sender(value: str | None) -> None:
    environ = {"EMAIL_BACKEND": "resend", "RESEND_API_KEY": "re_x"}
    if value is not None:
        environ["EMAIL_FROM"] = value
    assert error_lines(environ) == [C8]


def test_c8_render_requires_a_sender() -> None:
    environ = {k: v for k, v in RENDER_OK.items() if k != "EMAIL_FROM"}
    assert error_lines(environ) == [C8]


@pytest.mark.parametrize("sender", ["login@example.org", "Display Name <addr@example.org>"])
def test_c8_both_sender_forms_are_accepted(sender: str) -> None:
    assert resolve_auth_settings({**RENDER_OK, "EMAIL_FROM": sender}).email_from == sender


def test_render_with_nothing_set_names_every_setting_in_one_error() -> None:
    assert error_lines({"RENDER": "true"}) == [C2, C3, C5, C7, C8]


def test_every_violation_is_reported_together_in_rule_order() -> None:
    environ = {"EMAIL_BACKEND": "nope", "SECRET_KEY": "short", "ADMIN_EMAILS": "x"}
    assert error_lines(environ) == [
        C1,
        C4,
        "ADMIN_EMAILS entry 1 is not a valid email address.",
    ]


# ---------------------------------------------------------------------------------------------
# Rules C9–C10: the teacher and student lists (milestone 5)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["TEACHER_EMAILS", "STUDENT_EMAILS"])
@pytest.mark.parametrize("render", [False, True])
def test_c9_c10_malformed_entries_are_reported_by_position(name: str, render: bool) -> None:
    base = dict(RENDER_OK) if render else {}
    assert error_lines({**base, name: "ok@example.org,bad,also@@bad"}) == [
        f"{name} entry 2 is not a valid email address.",
        f"{name} entry 3 is not a valid email address.",
    ]


def test_the_new_lists_are_optional_on_render() -> None:
    """FR-036: a valid Render configuration without them starts."""
    settings = resolve_auth_settings(RENDER_OK)
    assert settings.teacher_emails == ()
    assert settings.student_emails == ()
    with_lists = {**RENDER_OK, "TEACHER_EMAILS": "t@example.org", "STUDENT_EMAILS": ""}
    assert resolve_auth_settings(with_lists).teacher_emails == ("t@example.org",)


def test_every_list_is_reported_in_one_error_in_rule_order() -> None:
    environ = {
        "EMAIL_BACKEND": "nope",
        "ADMIN_EMAILS": "bad",
        "TEACHER_EMAILS": "bad",
        "STUDENT_EMAILS": "ok@example.org,bad",
    }
    assert error_lines(environ) == [
        C1,
        "ADMIN_EMAILS entry 1 is not a valid email address.",
        "TEACHER_EMAILS entry 1 is not a valid email address.",
        "STUDENT_EMAILS entry 2 is not a valid email address.",
    ]


# ---------------------------------------------------------------------------------------------
# Warnings W1–W4
# ---------------------------------------------------------------------------------------------


def test_w1_w2_w4_warn_locally_when_unset(caplog: pytest.LogCaptureFixture) -> None:
    """With no list at all, W4 replaces W3."""
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        resolve_auth_settings({})
    assert warnings(caplog) == [W1, W2, W4]


@pytest.mark.parametrize("name", ["TEACHER_EMAILS", "STUDENT_EMAILS"])
def test_w3_warns_when_only_the_administrators_are_missing(
    name: str, caplog: pytest.LogCaptureFixture
) -> None:
    environ = {"SECRET_KEY": GOOD_KEY, "EMAIL_BACKEND": "memory", name: "a@example.org"}
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        resolve_auth_settings(environ)
    assert warnings(caplog) == [W3]


def test_no_warning_when_everything_is_set_locally(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        resolve_auth_settings(
            {"SECRET_KEY": GOOD_KEY, "EMAIL_BACKEND": "memory", "ADMIN_EMAILS": "a@x.org"}
        )
    assert warnings(caplog) == []


def test_no_warning_on_render(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=WARNING_LOGGER):
        resolve_auth_settings(RENDER_OK)
    assert warnings(caplog) == []


# ---------------------------------------------------------------------------------------------
# The no-echo rule
# ---------------------------------------------------------------------------------------------

PLANTED_SHORT_SECRET = "plantedsecret-0123456789"
PLANTED_LONG_SECRET = "plantedsecret-0123456789-abcdefghij"
PLANTED_KEY = "re_planted_key"


def assert_nothing_planted(text: str) -> None:
    for planted in ("plantedsecret", PLANTED_KEY, "planted@@bad", "planted-from"):
        assert planted not in text
    assert "planted" not in text, "no planted value of any list may appear"


@pytest.mark.parametrize("render", [False, True])
def test_no_value_appears_in_an_error_or_a_log(
    render: bool, caplog: pytest.LogCaptureFixture
) -> None:
    environ = {
        "EMAIL_BACKEND": "resend",
        "SECRET_KEY": PLANTED_SHORT_SECRET,
        "RESEND_API_KEY": PLANTED_KEY,
        "ADMIN_EMAILS": "planted@@bad",
        "TEACHER_EMAILS": "teacher-planted@@bad",
        "STUDENT_EMAILS": "student-planted@@bad",
        "EMAIL_FROM": "planted-from",
    }
    if render:
        environ["RENDER"] = "true"
    with caplog.at_level(logging.DEBUG), pytest.raises(AuthConfigError) as caught:
        resolve_auth_settings(environ)
    assert_nothing_planted(str(caught.value))
    for record in caplog.records:
        assert_nothing_planted(record.getMessage())


def test_repr_masks_the_secrets(caplog: pytest.LogCaptureFixture) -> None:
    environ = {
        **RENDER_OK,
        "SECRET_KEY": PLANTED_LONG_SECRET,
        "RESEND_API_KEY": PLANTED_KEY,
        "TEACHER_EMAILS": "teacher-planted@example.org,other@example.org",
        "STUDENT_EMAILS": "student-planted@example.org",
    }
    with caplog.at_level(logging.DEBUG):
        settings = resolve_auth_settings(environ)
    assert isinstance(settings, AuthSettings)
    assert_nothing_planted(repr(settings))
    assert_nothing_planted(str(settings))
    assert "@" not in repr(settings)
    for counted in ("admin_emails=<1 addresses>", "teacher_emails=<2 addresses>"):
        assert counted in repr(settings)
    assert "student_emails=<1 addresses>" in repr(settings)
    for record in caplog.records:
        assert_nothing_planted(record.getMessage())
