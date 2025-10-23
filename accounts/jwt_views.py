from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .authentication import set_jwt_cookies


class CookieTokenRefreshView(TokenRefreshView):
    """
    Custom JWT refresh view that reads refresh token from HttpOnly cookies
    """
    
    def post(self, request, *args, **kwargs):
        # Get refresh token from cookie
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh token not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Validate and create new tokens
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)
            
            # Create response with new tokens in cookies
            response = Response({'access': new_access_token})
            return set_jwt_cookies(response, new_access_token, new_refresh_token)
            
        except (InvalidToken, TokenError) as e:
            return Response(
                {'error': 'Invalid refresh token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
