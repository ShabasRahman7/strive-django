from rest_framework import serializers
from .models import Order, OrderItem, CartItem, WishlistItem, OrderPayment
from products.serializers import ProductListSerializer
from accounts.serializers import AddressSerializer
from accounts.models import Address


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price', 'total_price', 'created_at']
        read_only_fields = ['id', 'price', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    shipping_address_id = serializers.IntegerField(write_only=True, required=False)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'status', 'payment_method',
            'shipping_address', 'shipping_address_id', 'total_amount',
            'items', 'payment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'user', 'created_at', 'updated_at']

    def get_payment(self, obj):
        p = getattr(obj, 'payment', None)
        if not p:
            return None
        return {
            'provider': p.provider,
            'amount': str(p.amount),
            'currency': p.currency,
            'status': p.status,
            'method': p.method,
            'razorpay_order_id': p.razorpay_order_id,
            'razorpay_payment_id': p.razorpay_payment_id,
            'created_at': p.created_at,
        }


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating orders from cart items"""
    shipping_address_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES)

    def validate_shipping_address_id(self, value):
        user = self.context['request'].user
        try:
            address = user.addresses.get(id=value)
            return value
        except Address.DoesNotExist:
            raise serializers.ValidationError("Invalid shipping address")



