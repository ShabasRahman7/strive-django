from rest_framework import serializers
from .models import Order, OrderItem, CartItem, WishlistItem, OrderPayment
from products.serializers import ProductListSerializer
from accounts.serializers import AddressSerializer
from accounts.models import Address, User


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


# Admin-specific serializers for order management
class AdminOrderItemSerializer(serializers.ModelSerializer):
    """Admin serializer for order items with product details"""
    product = ProductListSerializer(read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'total_price', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdminOrderSerializer(serializers.ModelSerializer):
    """Admin serializer for orders with full details"""
    items = AdminOrderItemSerializer(many=True, read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    payment = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'status', 'payment_method',
            'shipping_address', 'total_amount', 'items', 'payment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']

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
            'razorpay_signature': p.razorpay_signature,
            'created_at': p.created_at,
        }

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'name': obj.user.get_full_name() or obj.user.username,
            'email': obj.user.email,
            'username': obj.user.username
        }


class AdminOrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin to update order status"""
    
    class Meta:
        model = Order
        fields = ['status']
        
    def validate_status(self, value):
        # Prevent changing status of delivered orders
        if self.instance and self.instance.status == 'delivered' and value != 'delivered':
            raise serializers.ValidationError("Cannot change the status of a delivered order.")
        return value


class AdminOrderListSerializer(serializers.ModelSerializer):
    """Simplified serializer for order list view"""
    user = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'status', 'payment_method',
            'total_amount', 'items_count', 'payment_status', 'payment_id',
            'shipping_address', 'created_at'
        ]

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'name': obj.user.get_full_name() or obj.user.username,
            'email': obj.user.email
        }

    def get_items_count(self, obj):
        return obj.items.count()

    def get_payment_status(self, obj):
        p = getattr(obj, 'payment', None)
        return p.status if p else 'pending'

    def get_payment_id(self, obj):
        p = getattr(obj, 'payment', None)
        if p:
            return p.razorpay_payment_id or p.razorpay_order_id
        return None

    def get_shipping_address(self, obj):
        if obj.shipping_address:
            return {
                'line1': obj.shipping_address.line1,
                'line2': obj.shipping_address.line2,
                'city': obj.shipping_address.city,
                'state': obj.shipping_address.state,
                'pin_code': obj.shipping_address.pin_code,
                'address_type': obj.shipping_address.address_type,
                'full_address': f"{obj.shipping_address.line1}, {obj.shipping_address.line2 or ''}, {obj.shipping_address.city}, {obj.shipping_address.state} - {obj.shipping_address.pin_code}".replace(', ,', ',')
            }
        return None



