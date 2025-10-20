from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.http import JsonResponse


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that reads tokens from HttpOnly cookies
    """
    
    def authenticate(self, request):
        # Try to get token from cookie first
        access_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        
        if access_token:
            try:
                # Validate the token
                validated_token = self.get_validated_token(access_token)
                user = self.get_user(validated_token)
                return (user, validated_token)
            except (InvalidToken, TokenError):
                # Token is invalid, try to refresh
                return self._try_refresh_token(request)
        
        # No access token, try to refresh
        return self._try_refresh_token(request)
    
    def _try_refresh_token(self, request):
        """Try to refresh the access token using refresh token from cookie"""
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        
        if not refresh_token:
            return None
            
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            
            # Validate the new access token
            validated_token = self.get_validated_token(access_token)
            user = self.get_user(validated_token)
            
            # Store the new access token in request for response
            request._new_access_token = access_token
            
            return (user, validated_token)
        except (InvalidToken, TokenError):
            return None


def set_jwt_cookies(response, access_token, refresh_token=None):
    """
    Set JWT tokens as HttpOnly cookies in the response
    """
    # Set access token cookie
    response.set_cookie(
        key=settings.SIMPLE_JWT['AUTH_COOKIE'],
        value=access_token,
        max_age=settings.SIMPLE_JWT['AUTH_COOKIE_ACCESS_MAX_AGE'],
        secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
        httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
        samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
        path='/'
    )
    
    # Set refresh token cookie if provided
    if refresh_token:
        response.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
            value=refresh_token,
            max_age=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH_MAX_AGE'],
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            path='/'
        )
    
    return response


def clear_jwt_cookies(response):
    """
    Clear JWT cookies from the response
    """
    response.delete_cookie(
        key=settings.SIMPLE_JWT['AUTH_COOKIE'],
        path='/',
        samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
    )
    response.delete_cookie(
        key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
        path='/',
        samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
    )
    
    return response




