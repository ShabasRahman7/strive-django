from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction, models
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .models import User, Address, PasswordResetToken, PendingSignup, PasswordSetupToken
from orders.models import CartItem, WishlistItem
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLoginSerializer, 
    UserProfileSerializer, AddressSerializer, AdminUserSerializer, AdminUserUpdateSerializer,
    AdminUserCreateSerializer, PasswordSetupSerializer
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
        elif self.action in ['admin_list', 'admin_retrieve', 'admin_update', 'admin_destroy']:
            # Admin-only actions
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Optimized queryset with proper filtering"""
        if self.action in ['admin_list', 'admin_retrieve', 'admin_update', 'admin_destroy']:
            # Admin can see all users except other admins
            return User.objects.filter(role='user').select_related().prefetch_related(
                'addresses', 'cart_items__product__images', 'wishlist_items__product__images'
            )
        elif self.request.user.is_authenticated:
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
            
            # Check if user is admin-added and hasn't set password yet
            if user.is_admin_added and not user.has_usable_password():
                return Response({
                    'error': 'Password setup required',
                    'message': 'Please check your email for password setup instructions',
                    'requires_password_setup': True
                }, status=status.HTTP_403_FORBIDDEN)
            
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

    # Admin User Management Methods

    @action(detail=False, methods=['get'], url_path='admin/list')
    def admin_list(self, request):
        """Admin endpoint to list all users with filtering"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get query parameters
        search = request.query_params.get('search', '')
        status_filter = request.query_params.get('status', 'all')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        # Filter users
        users = User.objects.filter(role='user').select_related()
        
        # Apply search filter
        if search:
            users = users.filter(
                models.Q(email__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(username__icontains=search)
            )
        
        # Apply status filter
        if status_filter == 'active':
            users = users.filter(is_blocked=False)
        elif status_filter == 'blocked':
            users = users.filter(is_blocked=True)
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_users = users[start:end]
        
        # Serialize users
        serializer = AdminUserSerializer(paginated_users, many=True)
        
        return Response({
            'users': serializer.data,
            'total': users.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (users.count() + page_size - 1) // page_size
        })

    @action(detail=True, methods=['get'], url_path='admin/detail')
    def admin_retrieve(self, request, pk=None):
        """Admin endpoint to get individual user details"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk, role='user')
            serializer = AdminUserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['patch'], url_path='admin/update')
    def admin_update(self, request, pk=None):
        """Admin endpoint to update user details"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk, role='user')
            serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                # Return updated user data
                updated_user = User.objects.get(id=pk)
                response_serializer = AdminUserSerializer(updated_user)
                return Response(response_serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'], url_path='admin/delete')
    def admin_destroy(self, request, pk=None):
        """Admin endpoint to delete users"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk)
            
            # Prevent deletion of superusers and staff users
            if user.is_superuser:
                return Response({'error': 'Cannot delete superuser accounts'}, status=status.HTTP_400_BAD_REQUEST)
            
            if user.is_staff and user.role != 'user':
                return Response({'error': 'Cannot delete staff accounts'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Only allow deletion of regular users
            if user.role != 'user':
                return Response({'error': 'Can only delete regular user accounts'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle foreign key constraints by clearing related data first
            try:
                # Clear admin log entries for this user (most important for deletion)
                # Only try this if admin app is installed
                from django.apps import apps
                if apps.is_installed('django.contrib.admin'):
                    from django.contrib.admin.models import LogEntry
                    LogEntry.objects.filter(user=user).delete()
                    print(f"Cleared admin log entries for user {user.id}")
                else:
                    print("Admin app not installed, skipping admin log cleanup")
            except Exception as e:
                print(f"Warning: Could not clear admin log entries: {e}")
            
            # Delete related objects that might have foreign key constraints
            try:
                # Delete password reset tokens
                PasswordResetToken.objects.filter(user=user).delete()
                PasswordSetupToken.objects.filter(user=user).delete()
                PendingSignup.objects.filter(email=user.email).delete()
                
                # Delete orders and related items
                from orders.models import Order, CartItem, WishlistItem
                CartItem.objects.filter(user=user).delete()
                WishlistItem.objects.filter(user=user).delete()
                Order.objects.filter(user=user).delete()
                
                # Clear user groups and permissions
                user.groups.clear()
                user.user_permissions.clear()
                
                # Delete addresses
                user.addresses.all().delete()
                
                # Clear any session data
                from django.contrib.sessions.models import Session
                Session.objects.filter(session_data__contains=f'"_auth_user_id":"{user.id}"').delete()
                
            except Exception as e:
                print(f"Warning: Error clearing related data: {e}")
                pass
            
            # Now delete the user with proper foreign key handling
            try:
                # Use raw SQL to handle foreign key constraints if needed
                from django.db import connection
                from django.apps import apps
                
                if apps.is_installed('django.contrib.admin'):
                    with connection.cursor() as cursor:
                        # First, set any remaining foreign key references to NULL or delete them
                        cursor.execute("""
                            UPDATE django_admin_log 
                            SET user_id = NULL 
                            WHERE user_id = %s
                        """, [user.id])
                
                # Now delete the user
                user.delete()
                return Response({'message': 'User deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                # If raw SQL fails, try the standard deletion
                try:
                    user.delete()
                    return Response({'message': 'User deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
                except Exception as delete_error:
                    return Response({
                        'error': f'Failed to delete user due to foreign key constraints: {str(delete_error)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Failed to delete user: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='admin/create')
    def admin_create(self, request):
        """Admin endpoint to create new users"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Create password setup token
            token = str(uuid.uuid4())
            PasswordSetupToken.objects.create(user=user, token=token)
            
            # Send password setup email
            email_sent = False
            try:
                setup_url = f"{settings.FRONTEND_URL}/setup-password?token={token}"
                send_mail(
                    'Set Your Password - Strive Store',
                    f'''
                    Hello {user.first_name or user.username},
                    
                    An admin has created an account for you. Please set your password by clicking the link below:
                    
                    {setup_url}
                    
                    This link will expire in 24 hours.
                    
                    Best regards,
                    Strive Store Team
                    ''',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                # Log error but don't fail user creation
                print(f"Failed to send password setup email: {e}")
            
            response_message = 'User created successfully.'
            if email_sent:
                response_message += ' Password setup email sent.'
            else:
                response_message += ' Note: Email could not be sent. Please check email configuration.'
            
            return Response({
                'message': response_message,
                'user': AdminUserSerializer(user).data,
                'setup_token': token if not email_sent else None  # Include token if email failed
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='setup-password')
    def setup_password(self, request):
        """Endpoint for users to set their password using setup token"""
        token = request.data.get('token')
        password = request.data.get('password')
        
        if not token or not password:
            return Response({'error': 'Token and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            setup_token = PasswordSetupToken.objects.get(token=token, is_used=False)
            
            # Check if token is expired
            if setup_token.is_expired():
                return Response({'error': 'Setup token has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user = setup_token.user
            
            # Set password and activate user
            user.set_password(password)
            user.is_active = True
            user.is_admin_added = False  # User is now self-managed
            user.save()
            
            # Mark token as used
            setup_token.is_used = True
            setup_token.save()
            
            return Response({
                'message': 'Password set successfully. You can now log in.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.first_name or user.username
                }
            }, status=status.HTTP_200_OK)
            
        except PasswordSetupToken.DoesNotExist:
            return Response({'error': 'Invalid or expired setup token'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='admin/edit')
    def admin_edit(self, request, pk=None):
        """Admin endpoint to edit user details"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk, role='user')
            serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'User updated successfully',
                    'user': AdminUserSerializer(user).data
                })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='admin/unactivated')
    def admin_unactivated_users(self, request):
        """Admin endpoint to list unactivated admin-added users"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get query parameters
        search = request.query_params.get('search', '')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        # Filter unactivated admin-added users (no usable password)
        users = User.objects.filter(is_admin_added=True).select_related()
        
        # Filter out users with usable passwords
        unactivated_users = []
        for user in users:
            if not user.has_usable_password():
                unactivated_users.append(user)
        
        users = unactivated_users
        
        # Apply search filter
        if search:
            filtered_users = []
            for user in users:
                if (search.lower() in user.email.lower() or
                    search.lower() in (user.first_name or '').lower() or
                    search.lower() in (user.last_name or '').lower() or
                    search.lower() in user.username.lower()):
                    filtered_users.append(user)
            users = filtered_users
        
        # Order by creation date (newest first)
        users = sorted(users, key=lambda x: x.created_at, reverse=True)
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_users = users[start:end]
        
        # Serialize users
        serializer = AdminUserSerializer(paginated_users, many=True)
        
        return Response({
            'users': serializer.data,
            'total': len(users),
            'page': page,
            'page_size': page_size,
            'total_pages': (len(users) + page_size - 1) // page_size
        })

    @action(detail=True, methods=['post'], url_path='admin/resend-setup')
    def admin_resend_setup(self, request, pk=None):
        """Admin endpoint to resend password setup email"""
        if not request.user.is_authenticated or request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=pk, role='user', is_admin_added=True)
            
            # Check if user already has a usable password
            if user.has_usable_password():
                return Response({
                    'error': 'User already has a password set'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create new password setup token
            token = str(uuid.uuid4())
            PasswordSetupToken.objects.create(user=user, token=token)
            
            # Send password setup email
            try:
                setup_url = f"{settings.FRONTEND_URL}/setup-password?token={token}"
                send_mail(
                    'Set Your Password - Strive Store',
                    f'''
                    Hello {user.first_name or user.username},
                    
                    An admin has created an account for you. Please set your password by clicking the link below:
                    
                    {setup_url}
                    
                    This link will expire in 24 hours.
                    
                    Best regards,
                    Strive Store Team
                    ''',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                
                return Response({
                    'message': 'Password setup email sent successfully'
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'error': f'Failed to send email: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


@method_decorator(csrf_exempt, name='dispatch')
class PasswordSetupViewSet(viewsets.ViewSet):
    """ViewSet for password setup by admin-added users"""
    permission_classes = [permissions.AllowAny]
    queryset = PasswordSetupToken.objects.none()  # Empty queryset since we don't need it
    
    @action(detail=False, methods=['post'], url_path='validate')
    def validate_token(self, request):
        """Validate password setup token"""
        token = request.data.get('token')
        
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            setup_token = PasswordSetupToken.objects.get(token=token, is_used=False)
            
            # Check if token is expired
            if setup_token.is_expired():
                return Response({'error': 'Setup token has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': 'Token is valid',
                'user': {
                    'id': setup_token.user.id,
                    'email': setup_token.user.email,
                    'name': setup_token.user.first_name or setup_token.user.username
                }
            }, status=status.HTTP_200_OK)
            
        except PasswordSetupToken.DoesNotExist:
            return Response({'error': 'Invalid or expired setup token'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='setup')
    def setup_password(self, request):
        """Setup password for admin-added users"""
        serializer = PasswordSetupSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            password = serializer.validated_data['password']
            
            try:
                # Get the token object
                token_obj = PasswordSetupToken.objects.get(token=token, is_used=False)
                
                # Check if token is expired
                if token_obj.is_expired():
                    return Response({'error': 'Setup token has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
                
                user = token_obj.user
                
                # Set the password and activate user
                user.set_password(password)
                user.is_active = True
                user.is_admin_added = False  # User is now self-managed
                user.save()
                
                # Mark token as used
                token_obj.is_used = True
                token_obj.save()
                
                return Response({
                    'message': 'Password set successfully. You can now login.'
                }, status=status.HTTP_200_OK)
                
            except PasswordSetupToken.DoesNotExist:
                return Response({'error': 'Invalid or expired setup token'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


@api_view(['POST'])
@permission_classes([AllowAny])
def setup_password_view(request):
    """Standalone endpoint for users to set their password using setup token"""
    token = request.data.get('token')
    password = request.data.get('password')
    
    if not token or not password:
        return Response({'error': 'Token and password are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        setup_token = PasswordSetupToken.objects.get(token=token, is_used=False)
        
        # Check if token is expired
        if setup_token.is_expired():
            return Response({'error': 'Setup token has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = setup_token.user
        
        # Set password and activate user
        user.set_password(password)
        user.is_active = True
        user.is_admin_added = False  # User is now self-managed
        user.save()
        
        # Mark token as used
        setup_token.is_used = True
        setup_token.save()
        
        return Response({
            'message': 'Password set successfully. You can now log in.',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.first_name or user.username
            }
        }, status=status.HTTP_200_OK)
        
    except PasswordSetupToken.DoesNotExist:
        return Response({'error': 'Invalid or expired setup token'}, status=status.HTTP_400_BAD_REQUEST)
