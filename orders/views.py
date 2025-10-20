from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db import transaction
from django.conf import settings
from rest_framework.views import APIView
import uuid
import razorpay

from .models import Order, OrderItem, CartItem, WishlistItem, OrderPayment
from .serializers import (
    OrderSerializer,
    OrderItemSerializer,
    CartItemSerializer,
    WishlistItemSerializer,
    CreateOrderSerializer,
)


class OrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


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
        """Create a Razorpay order for the current cart total and return order details."""
        # Calculate amount from user's cart
        cart_items = CartItem.objects.filter(user=request.user)
        if not cart_items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        amount = int(sum(item.product.price * item.quantity for item in cart_items) * 100)  # in paise
        currency = 'INR'

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({'error': 'Razorpay keys not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
        try:
            order = client.order.create({
                'amount': amount,
                'currency': currency,
                'receipt': receipt_id,
                'payment_capture': 1,
            })
            return Response({
                'order_id': order.get('id'),
                'amount': amount,
                'currency': currency,
                'key_id': settings.RAZORPAY_KEY_ID,
                'receipt': receipt_id,
            })
        except Exception as e:
            return Response({'error': 'Razorpay order creation failed', 'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


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
