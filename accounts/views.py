from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .models import User, Address, PasswordResetToken, PendingSignup
from orders.models import CartItem, WishlistItem
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLoginSerializer, 
    UserProfileSerializer, AddressSerializer
)
from .authentication import set_jwt_cookies, clear_jwt_cookies


class UserViewSet(viewsets.ModelViewSet):
    """
    Optimized UserViewSet with efficient queryset and proper permissions
    - Uses select_related/prefetch_related for performance
    - Implements proper permission classes per action
    - Includes cart/wishlist management actions
    """
    queryset = User.objects.select_related().prefetch_related('addresses', 'cart_items__product', 'wishlist_items__product')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Dynamic permissions based on action"""
        if self.action in ['register', 'login', 'logout', 'profile', 'update_profile', 'cart', 'wishlist', 'add_address', 'delete_address']:
            permission_classes = [permissions.AllowAny] if self.action in ['register', 'login', 'logout'] else [permissions.IsAuthenticated]
        elif self.action in ['forgot_password', 'reset_password']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Optimized queryset with proper filtering"""
        if self.request.user.is_authenticated:
            return User.objects.filter(id=self.request.user.id).select_related().prefetch_related(
                'addresses', 'cart_items__product__images', 'wishlist_items__product__images'
            )
        return User.objects.none()

    def retrieve(self, request, *args, **kwargs):
        """Handle individual user retrieval for frontend compatibility"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Only allow requesting own profile
        user_id = kwargs.get('pk')
        if str(request.user.id) == str(user_id):
            user = self.get_object()
            return Response({
                'id': user.id,
                'email': user.email,
                'name': user.first_name or user.username,
                'role': user.role,
                'isBlocked': user.is_blocked,
                'profileImage': user.profile_image or 'https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp',
                'addresses': [{'id': addr.id, 'line1': addr.line1, 'line2': addr.line2, 'city': addr.city, 'state': addr.state, 'pin': addr.pin_code, 'type': addr.address_type} for addr in user.addresses.all()],
                'cart': [{'id': item.product.id, 'name': item.product.name, 'price': float(item.product.price), 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file], 'quantity': item.quantity} for item in user.cart_items.all()],
                'wishlist': [{'id': item.product.id, 'name': item.product.name, 'description': item.product.description, 'price': float(item.product.price), 'count': item.product.stock_count, 'category': item.product.category.name, 'isActive': item.product.is_active, 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file]} for item in user.wishlist_items.all()],
                'orders': []
            })
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        return Response({'error': 'Not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                'id': user.id,
                'email': user.email,
                'name': user.first_name or user.username,
                'role': user.role,
                'isBlocked': user.is_blocked,
                'profileImage': user.profile_image or 'https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp',
                'addresses': [],
                'cart': [],
                'wishlist': [],
                'orders': []
            }
            
            response = Response(response_data, status=status.HTTP_201_CREATED)
            return set_jwt_cookies(response, str(refresh.access_token), str(refresh))
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({'error': 'Email and password required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                if user.is_blocked:
                    return Response({'error': 'Account is blocked'}, status=status.HTTP_403_FORBIDDEN)
                
                refresh = RefreshToken.for_user(user)
                
                response_data = {
                    'id': user.id,
                    'email': user.email,
                    'name': user.first_name or user.username,
                    'role': user.role,
                    'isBlocked': user.is_blocked,
                    'profileImage': user.profile_image or 'https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp',
                    'addresses': [{'id': addr.id, 'line1': addr.line1, 'line2': addr.line2, 'city': addr.city, 'state': addr.state, 'pin': addr.pin_code, 'type': addr.address_type} for addr in user.addresses.all()],
                    'cart': [{'id': item.product.id, 'name': item.product.name, 'price': float(item.product.price), 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file], 'quantity': item.quantity} for item in user.cart_items.all()],
                    'wishlist': [{'id': item.product.id, 'name': item.product.name, 'description': item.product.description, 'price': float(item.product.price), 'count': item.product.stock_count, 'category': item.product.category.name, 'isActive': item.product.is_active, 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file]} for item in user.wishlist_items.all()],
                    'orders': []
                }
                
                response = Response(response_data)
                return set_jwt_cookies(response, str(refresh.access_token), str(refresh))
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def logout(self, request):
        response = Response({'message': 'Logged out successfully'})
        return clear_jwt_cookies(response)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def profile(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if request.method == 'PATCH':
            # Build a safe mutable dict without deep-copying uploaded files
            data = {}
            name_value = request.data.get('name')
            if name_value is not None:
                data['first_name'] = name_value
            
            # Handle profile image file upload only
            file_obj = request.FILES.get('profile_image')
            if file_obj:
                path = f"profiles/{request.user.id}/{file_obj.name}"
                saved_path = default_storage.save(path, ContentFile(file_obj.read()))
                file_url = request.build_absolute_uri(default_storage.url(saved_path))
                data['profile_image'] = file_url
            
            serializer = UserProfileSerializer(request.user, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'name': user.first_name or user.username,
            'role': user.role,
            'isBlocked': user.is_blocked,
            'profileImage': user.profile_image or 'https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp',
            'addresses': [{'id': addr.id, 'line1': addr.line1, 'line2': addr.line2, 'city': addr.city, 'state': addr.state, 'pin': addr.pin_code, 'type': addr.address_type} for addr in user.addresses.all()],
            'cart': [{'id': item.product.id, 'name': item.product.name, 'price': float(item.product.price), 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file], 'quantity': item.quantity} for item in user.cart_items.all()],
            'wishlist': [{'id': item.product.id, 'name': item.product.name, 'description': item.product.description, 'price': float(item.product.price), 'count': item.product.stock_count, 'category': item.product.category.name, 'isActive': item.product.is_active, 'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file]} for item in user.wishlist_items.all()],
            'orders': []
        })

    # Removed separate update_profile; PATCH is handled in profile action above

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_address(self, request):
        """Add new address for current user"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Map frontend alias fields to serializer fields
        data = request.data.copy()
        if 'pin' in data:
            data['pin_code'] = data.pop('pin')
        if 'type' in data:
            data['address_type'] = data.pop('type')

        serializer = AddressSerializer(data=data)
        if serializer.is_valid():
            address = serializer.save(user=request.user)
            return Response({
                'id': address.id,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'state': address.state,
                'pin': address.pin_code,
                'type': address.address_type
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated])
    def delete_address(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        address_id = request.data.get('address_id')
        if not address_id:
            return Response({'error': 'address_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            address = Address.objects.get(id=address_id, user=request.user)
            address.delete()
            return Response({'message': 'Address deleted successfully'})
        except Address.DoesNotExist:
            return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def cart(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if request.method == 'GET':
            cart_items = request.user.cart_items.select_related('product').prefetch_related('product__images')
            return Response([{
                'id': item.product.id,
                'name': item.product.name,
                'price': float(item.product.price),
                'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file],
                'quantity': item.quantity
            } for item in cart_items])
        
        elif request.method == 'PATCH':
            cart_data = request.data.get('cart', [])
            with transaction.atomic():
                # Clear existing cart
                request.user.cart_items.all().delete()
                # Add new cart items
                for item in cart_data:
                    from products.models import Product
                    try:
                        product = Product.objects.get(id=item['id'])
                        CartItem.objects.create(
                            user=request.user,
                            product=product,
                            quantity=item.get('quantity', 1)
                        )
                    except Product.DoesNotExist:
                        continue
            return Response({'success': True})

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def wishlist(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if request.method == 'GET':
            wishlist_items = request.user.wishlist_items.select_related('product').prefetch_related('product__images')
            return Response([{
                'id': item.product.id,
                'name': item.product.name,
                'description': item.product.description,
                'price': float(item.product.price),
                'count': item.product.stock_count,
                'category': item.product.category.name,
                'isActive': item.product.is_active,
                'images': [img.image_url_or_file for img in item.product.images.all() if img.image_url_or_file]
            } for item in wishlist_items])
        
        elif request.method == 'PATCH':
            wishlist_data = request.data.get('wishlist', [])
            with transaction.atomic():
                # Clear existing wishlist
                request.user.wishlist_items.all().delete()
                # Add new wishlist items
                for item in wishlist_data:
                    from products.models import Product
                    try:
                        product = Product.objects.get(id=item['id'])
                        WishlistItem.objects.create(
                            user=request.user,
                            product=product
                        )
                    except Product.DoesNotExist:
                        continue
            return Response({'success': True})


class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response({'message': 'Address set as default'})



# Function-based views for password reset (bypass ViewSet authentication)
from django.http import JsonResponse
import random

@csrf_exempt
def forgot_password_view(request):
    """Send password reset email - function-based view"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            try:
                user = User.objects.get(email=email)
                # Generate unique token
                token = str(uuid.uuid4())
                # Save token
                PasswordResetToken.objects.create(user=user, token=token)
                
                # Create reset link
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
                reset_link = f"{frontend_url}/reset-password?token={token}"
                
                # Send email
                send_mail(
                    subject='Password Reset - Strive Store',
                    message=f'Click the link to reset your password: {reset_link}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                return JsonResponse({'message': 'Password reset link sent to your email'})
                
            except User.DoesNotExist:
                return JsonResponse({'message': 'If email exists, reset link sent'})  # Don't reveal if user exists
            except Exception as e:
                return JsonResponse({'error': 'Failed to send reset email'}, status=500)
        except Exception as e:
            return JsonResponse({'error': 'Invalid request'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def reset_password_view(request):
    """Reset password using token - function-based view"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            token = data.get('token')
            new_password = data.get('new_password')
            
            if not token or not new_password:
                return JsonResponse({'error': 'Token and new password are required'}, status=400)
            
            try:
                reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
                user = reset_token.user
                
                # Update password
                user.set_password(new_password)
                user.save()
                
                # Mark token as used
                reset_token.is_used = True
                reset_token.save()
                
                return JsonResponse({'message': 'Password reset successfully'})
                
            except PasswordResetToken.DoesNotExist:
                return JsonResponse({'error': 'Invalid or expired reset token'}, status=400)
            except Exception as e:
                return JsonResponse({'error': 'Failed to reset password'}, status=500)
        except Exception as e:
            return JsonResponse({'error': 'Invalid request'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def register_request_view(request):
    """Start signup: accept name, email, password; send OTP; do not create user yet"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            name = data.get('name') or ''
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=400)

            # Prevent duplicate existing user
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'User with this email already exists'}, status=400)

            # Generate 6-digit OTP
            otp = f"{random.randint(100000, 999999)}"

            # Upsert pending signup
            username = (email.split('@')[0])[:150]
            PendingSignup.objects.update_or_create(
                email=email,
                defaults={
                    'username': username,
                    'name': name,
                    'password': password,
                    'otp': otp,
                    'attempts': 0,
                }
            )

            # Send OTP email
            send_mail(
                subject='Strive - Your Signup OTP',
                message=f'Your OTP is {otp}. Enter this to complete your signup.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            return JsonResponse({'message': 'OTP sent to your email'})
        except Exception:
            return JsonResponse({'error': 'Failed to process signup request'}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def register_verify_view(request):
    """Verify OTP and create the user account"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            email = data.get('email')
            otp = data.get('otp')

            if not email or not otp:
                return JsonResponse({'error': 'Email and OTP are required'}, status=400)

            try:
                pending = PendingSignup.objects.get(email=email)
            except PendingSignup.DoesNotExist:
                return JsonResponse({'error': 'No pending signup for this email'}, status=400)

            if str(pending.otp) != str(otp):
                pending.attempts = pending.attempts + 1
                pending.save(update_fields=['attempts'])
                return JsonResponse({'error': 'Invalid OTP'}, status=400)

            # Create user now
            user = User.objects.create(
                email=pending.email,
                username=pending.username,
                first_name=pending.name or pending.username,
            )
            user.set_password(pending.password)
            user.save()

            # Cleanup
            pending.delete()

            return JsonResponse({'message': 'Account created successfully'})
        except Exception:
            return JsonResponse({'error': 'Failed to verify OTP'}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
