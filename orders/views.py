from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db import transaction
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.decorators import permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import razorpay

from .models import Order, OrderItem, CartItem, WishlistItem, OrderPayment
from .serializers import (
    OrderSerializer,
    OrderItemSerializer,
    CartItemSerializer,
    WishlistItemSerializer,
    CreateOrderSerializer,
    AdminOrderSerializer,
    AdminOrderListSerializer,
    AdminOrderUpdateSerializer,
)


class AdminOrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class OrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class CancelOrderView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Only allow cancellation of pending orders
        if order.status != 'pending':
            return Response(
                {'error': 'Only pending orders can be cancelled'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)


class CreateOrderFromCartView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            cart_items = CartItem.objects.filter(user=request.user)
            if not cart_items.exists():
                return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

            total_amount = sum(item.product.price * item.quantity for item in cart_items)

            order = Order.objects.create(
                user=request.user,
                shipping_address_id=serializer.validated_data['shipping_address_id'],
                payment_method=serializer.validated_data['payment_method'],
                total_amount=total_amount,
            )

            for cart_item in cart_items:
                if cart_item.product.stock_count < cart_item.quantity:
                    return Response({'error': f'Insufficient stock for {cart_item.product.name}'}, status=status.HTTP_400_BAD_REQUEST)

                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price,
                )

                cart_item.product.stock_count -= cart_item.quantity
                cart_item.product.save()

            cart_items.delete()

            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RazorpayCreateOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            print("----RZP CREATE ORDER HIT----")
            print("USER:", request.user.id)

            cart_items = CartItem.objects.filter(user=request.user)
            print("CART COUNT:", cart_items.count())

            amount = int(sum(item.product.price * item.quantity for item in cart_items) * 100)
            print("AMOUNT:", amount)

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
            print("RECEIPT:", receipt_id)

            order = client.order.create({
                'amount': amount,
                'currency': 'INR',
                'receipt': receipt_id,
                'payment_capture': 1,
            })
            print("ORDER RESPONSE:", order)

            return Response({
                'order_id': order.get('id'),
                'amount': amount,
                'currency': 'INR',
                'key_id': settings.RAZORPAY_KEY_ID,
                'receipt': receipt_id,
            })

        except Exception as e:
            print("RZP ERROR =>", repr(e))   # <---- CRUCIAL LINE
            return Response({'error': 'Razorpay order creation failed', 'detail': str(e)}, status=502)
class RazorpayVerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Verify Razorpay signature and on success, create Order from cart."""
        rp_order_id = request.data.get('razorpay_order_id')
        rp_payment_id = request.data.get('razorpay_payment_id')
        rp_signature = request.data.get('razorpay_signature')
        shipping_address_id = request.data.get('shipping_address_id')
        payment_method = 'razorpay'

        if not all([rp_order_id, rp_payment_id, rp_signature, shipping_address_id]):
            return Response({'error': 'Missing payment verification fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': rp_order_id,
                'razorpay_payment_id': rp_payment_id,
                'razorpay_signature': rp_signature,
            })
        except Exception as e:
            return Response({'error': 'Payment verification failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # If verification passed, create order from cart
        with transaction.atomic():
            cart_items = CartItem.objects.filter(user=request.user)
            if not cart_items.exists():
                return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

            total_amount = sum(item.product.price * item.quantity for item in cart_items)

            order = Order.objects.create(
                user=request.user,
                shipping_address_id=shipping_address_id,
                payment_method=payment_method,
                total_amount=total_amount,
            )

            for cart_item in cart_items:
                if cart_item.product.stock_count < cart_item.quantity:
                    return Response({'error': f'Insufficient stock for {cart_item.product.name}'}, status=status.HTTP_400_BAD_REQUEST)

                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price,
                )

                cart_item.product.stock_count -= cart_item.quantity
                cart_item.product.save()

            cart_items.delete()

            # Save payment details linked to order
            try:
                OrderPayment.objects.create(
                    order=order,
                    provider='razorpay',
                    amount=total_amount,
                    currency='INR',
                    status='captured',
                    method='upi',
                    raw_payload={
                        'razorpay_order_id': rp_order_id,
                        'razorpay_payment_id': rp_payment_id,
                        'razorpay_signature': rp_signature,
                    },
                    razorpay_order_id=rp_order_id,
                    razorpay_payment_id=rp_payment_id,
                    razorpay_signature=rp_signature,
                )
            except Exception:
                pass

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CartListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartItemSerializer

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartItemSerializer

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)


class CartClearView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return None

    def delete(self, request, *args, **kwargs):
        CartItem.objects.filter(user=request.user).delete()
        return Response({"message": "Cart cleared"}, status=status.HTTP_200_OK)


class WishlistListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistItemSerializer

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistItemSerializer

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)


class WishlistClearView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return None

    def delete(self, request, *args, **kwargs):
        WishlistItem.objects.filter(user=request.user).delete()
        return Response({"message": "Wishlist cleared"}, status=status.HTTP_200_OK)

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import Order, OrderItem, CartItem, WishlistItem
from .serializers import (
    OrderSerializer, OrderItemSerializer, CartItemSerializer, 
    WishlistItemSerializer, CreateOrderSerializer
)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_admin:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def create_from_cart(self, request):
        """Create order from cart items"""
        serializer = CreateOrderSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            with transaction.atomic():
                # Get cart items
                cart_items = CartItem.objects.filter(user=request.user)
                if not cart_items.exists():
                    return Response(
                        {'error': 'Cart is empty'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calculate total amount
                total_amount = sum(
                    item.product.price * item.quantity for item in cart_items
                )

                # Create order
                order = Order.objects.create(
                    user=request.user,
                    shipping_address_id=serializer.validated_data['shipping_address_id'],
                    payment_method=serializer.validated_data['payment_method'],
                    total_amount=total_amount
                )

                # Create order items and update stock
                for cart_item in cart_items:
                    if cart_item.product.stock_count < cart_item.quantity:
                        return Response(
                            {'error': f'Insufficient stock for {cart_item.product.name}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price
                    )
                    
                    # Update stock
                    cart_item.product.stock_count -= cart_item.quantity
                    cart_item.product.save()

                # Clear cart
                cart_items.delete()

                return Response(
                    OrderSerializer(order).data, 
                    status=status.HTTP_201_CREATED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Remove unsafe mutation from user side; admin surface removed per requirements


class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all cart items"""
        CartItem.objects.filter(user=request.user).delete()
        return Response({'message': 'Cart cleared'})


class WishlistItemViewSet(viewsets.ModelViewSet):
    queryset = WishlistItem.objects.all()
    serializer_class = WishlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all wishlist items"""
        WishlistItem.objects.filter(user=request.user).delete()
        return Response({'message': 'Wishlist cleared'})


# Admin-only views for order management
class AdminOrderListView(generics.ListAPIView):
    """Admin view to list all orders with filtering and search"""
    serializer_class = AdminOrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = AdminOrderPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['order_number', 'user__email', 'user__username']
    ordering_fields = ['created_at', 'total_amount', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        # Only allow admin users
        if not self.request.user.is_admin:
            return Order.objects.none()
        return Order.objects.select_related('user', 'shipping_address', 'payment').prefetch_related('items__product')


class AdminOrderDetailView(generics.RetrieveAPIView):
    """Admin view to get detailed order information"""
    serializer_class = AdminOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow admin users
        if not self.request.user.is_admin:
            return Order.objects.none()
        return Order.objects.select_related('user', 'shipping_address', 'payment').prefetch_related('items__product')


class AdminOrderUpdateView(generics.UpdateAPIView):
    """Admin view to update order status"""
    serializer_class = AdminOrderUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow admin users
        if not self.request.user.is_admin:
            return Order.objects.none()
        return Order.objects.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': f'Order {instance.order_number} status updated to "{serializer.validated_data["status"]}"',
            'order': AdminOrderSerializer(instance).data
        })


class AdminOrderStatsView(APIView):
    """Admin view to get order statistics"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Only allow admin users
        if not request.user.is_admin:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        orders = Order.objects.all()
        
        # Calculate statistics
        total_orders = orders.count()
        total_revenue = sum(order.total_amount for order in orders)
        
        # Status counts
        status_counts = {}
        for status, _ in Order.STATUS_CHOICES:
            status_counts[status] = orders.filter(status=status).count()
        
        # Recent orders (last 10)
        recent_orders = orders.order_by('-created_at')[:10]
        recent_orders_data = AdminOrderListSerializer(recent_orders, many=True).data
        
        return Response({
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'status_counts': status_counts,
            'recent_orders': recent_orders_data
        })


class AdminDashboardView(APIView):
    """Comprehensive admin dashboard with all statistics"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Only allow admin users
        if not request.user.is_admin:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        from accounts.models import User
        from products.models import Product
        
        # Basic counts
        total_users = User.objects.filter(role='user').count()
        total_products = Product.objects.count()
        total_orders = Order.objects.count()
        total_revenue = Order.objects.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Revenue by year (2020-2025)
        yearly_revenue = {}
        for year in range(2020, 2026):
            year_orders = Order.objects.filter(
                created_at__year=year
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            yearly_revenue[str(year)] = float(year_orders)
        
        # Monthly revenue for current year
        current_year = timezone.now().year
        monthly_revenue = {}
        for month in range(1, 13):
            month_orders = Order.objects.filter(
                created_at__year=current_year,
                created_at__month=month
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            monthly_revenue[str(month)] = float(month_orders)
        
        # Order status
        status_counts = {}
        for status, _ in Order.STATUS_CHOICES:
            status_counts[status] = Order.objects.filter(status=status).count()
        
        # Low stock products < 5
        low_stock_products = Product.objects.filter(stock_count__lt=5).values(
            'id', 'name', 'stock_count'
        )[:10]
        
        # Recent orders last 5
        recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]
        recent_orders_data = []
        for order in recent_orders:
            recent_orders_data.append({
                'id': order.id,
                'order_number': order.order_number,
                'user': {
                    'name': order.user.first_name or order.user.username,
                    'email': order.user.email
                },
                'total_amount': float(order.total_amount),
                'status': order.status,
                'created_at': order.created_at.isoformat()
            })
        
        # Top selling products (by quantity sold)
        top_products = OrderItem.objects.values('product__name').annotate(
            total_sold=Sum('quantity')
        ).order_by('-total_sold')[:5]
        
        # Daily revenue for last 30 days
        daily_revenue = {}
        for i in range(30):
            date = timezone.now().date() - timedelta(days=i)
            day_orders = Order.objects.filter(
                created_at__date=date
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            daily_revenue[date.isoformat()] = float(day_orders)
        
        return Response({
            'summary': {
                'total_users': total_users,
                'total_products': total_products,
                'total_orders': total_orders,
                'total_revenue': float(total_revenue)
            },
            'yearly_revenue': yearly_revenue,
            'monthly_revenue': monthly_revenue,
            'daily_revenue': daily_revenue,
            'status_distribution': status_counts,
            'low_stock_products': list(low_stock_products),
            'recent_orders': recent_orders_data,
            'top_products': list(top_products)
        })
