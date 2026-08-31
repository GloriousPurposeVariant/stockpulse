from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import UserSerializer


def set_refresh_cookie(response, token):
    """Put the refresh token where JavaScript cannot reach it."""
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        # Persistent rather than session-scoped: closing the tab must not end
        # the session, and every tab shares this one cookie.
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
    )


class LoginView(TokenObtainPairView):
    """Credentials in, access token in the body, refresh token in a cookie.

    SimpleJWT's own view returns both tokens as JSON. Moving the refresh token
    into a cookie is the whole point of subclassing it.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # pop, not read: the refresh token must not also travel in the body,
            # or it lands in JavaScript and the cookie was pointless.
            set_refresh_cookie(response, response.data.pop("refresh"))
        return response


@method_decorator(csrf_protect, name="dispatch")
class RefreshView(TokenRefreshView):
    """Mint a new access token from the cookie.

    SimpleJWT expects the refresh token in the request body. The browser sends
    it as a cookie and JavaScript cannot read it, so the token is taken from
    there and handed to the serializer directly.
    """

    def post(self, request, *args, **kwargs):
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not token:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={"refresh": token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            # Expired, or blacklisted by a previous rotation. Clear the cookie
            # so the client stops retrying with something already dead.
            response = Response(
                {"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(settings.AUTH_COOKIE_NAME, path=settings.AUTH_COOKIE_PATH)
            raise InvalidToken(exc.args[0]) from exc

        data = serializer.validated_data
        response = Response({"access": data["access"]})
        # ROTATE_REFRESH_TOKENS is on, so the serializer hands back a new
        # refresh token and blacklists the old one. Failing to store the new
        # one means the *next* refresh presents a blacklisted token and the
        # user is logged out fifteen minutes later for no visible reason.
        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])
        return response


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    # Deliberately open. The access token may already have expired, and a user
    # trying to log out must always succeed - refusing would leave a live
    # refresh cookie in a browser whose owner asked to be signed out.
    permission_classes = (AllowAny,)

    def post(self, request):
        token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.AUTH_COOKIE_NAME, path=settings.AUTH_COOKIE_PATH)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                # Already expired or already blacklisted. The cookie is gone
                # either way, which is what the caller asked for.
                pass
        return response


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CsrfView(APIView):
    """Hand the SPA a CSRF cookie before it calls anything cookie-authenticated."""

    permission_classes = (AllowAny,)

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)
