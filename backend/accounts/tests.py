import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

pytestmark = pytest.mark.django_db

COOKIE = settings.AUTH_COOKIE_NAME


@pytest.fixture
def api():
    """A bare client. APIClient extends Django's test Client, so it keeps a
    cookie jar across requests - which is exactly the browser behaviour these
    tests are about."""
    return APIClient()


def login(api, user, password="pw"):
    return api.post(
        reverse("auth:login"), {"username": user.username, "password": password}, format="json"
    )


def test_login_returns_an_access_token_and_no_refresh_token(api, customer):
    response = login(api, customer)

    assert response.status_code == 200
    assert "access" in response.data
    # The refresh token must reach the browser only as a cookie. If it is also
    # in the body then JavaScript can read it and httpOnly bought nothing.
    assert "refresh" not in response.data


def test_login_sets_a_locked_down_refresh_cookie(api, customer):
    response = login(api, customer)

    cookie = response.cookies[COOKIE]
    assert cookie.value
    # The four properties the entire design rests on.
    assert cookie["httponly"] is True
    assert cookie["samesite"] == settings.AUTH_COOKIE_SAMESITE
    assert cookie["path"] == settings.AUTH_COOKIE_PATH
    # Persistent, not session-scoped: closing the tab must not sign the user out.
    assert int(cookie["max-age"]) > 0


def test_bad_credentials_set_no_cookie(api, customer):
    response = api.post(
        reverse("auth:login"),
        {"username": customer.username, "password": "wrong"},
        format="json",
    )

    assert response.status_code == 401
    assert COOKIE not in response.cookies


def test_refresh_works_with_the_cookie_alone(api, customer):
    login(api, customer)

    # No body. The browser sends nothing but the cookie, because JavaScript
    # cannot read the token to put it anywhere else.
    response = api.post(reverse("auth:refresh"))

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" not in response.data


def test_refresh_rotates_the_cookie_and_kills_the_old_token(api, customer):
    login(api, customer)
    original = api.cookies[COOKIE].value

    response = api.post(reverse("auth:refresh"))

    rotated = response.cookies[COOKIE].value
    assert rotated != original

    # Replay the old token the way a second browser tab would if it had read
    # the cookie before the rotation landed.
    api.cookies[COOKIE] = original
    replay = api.post(reverse("auth:refresh"))
    assert replay.status_code == 401


def test_refresh_without_a_cookie_is_rejected(api):
    response = api.post(reverse("auth:refresh"))

    assert response.status_code == 401


def test_logout_clears_the_cookie_and_blacklists_the_token(api, customer):
    login(api, customer)

    response = api.post(reverse("auth:logout"))

    assert response.status_code == 204
    # delete_cookie sets an empty value with an immediate expiry.
    assert response.cookies[COOKIE].value == ""
    # Clearing the cookie only ends the session in this browser. Blacklisting
    # ends it for anyone holding a copy.
    assert BlacklistedToken.objects.count() == 1


def test_me_returns_the_signed_in_user(client_for, customer):
    response = client_for(customer).get(reverse("auth:me"))

    assert response.status_code == 200
    assert response.data["username"] == customer.username
    # Named fields only. A serializer with __all__ would leak the hash.
    assert "password" not in response.data


def test_refresh_requires_a_csrf_token(customer):
    # Django's test client waives CSRF by default, which is why every other
    # test here ignores it. This one asks for the real thing.
    api = APIClient(enforce_csrf_checks=True)
    login(api, customer)

    unprotected = api.post(reverse("auth:refresh"))
    assert unprotected.status_code == 403

    api.get(reverse("auth:csrf"))
    token = api.cookies["csrftoken"].value
    protected = api.post(reverse("auth:refresh"), headers={"x-csrftoken": token})
    assert protected.status_code == 200
