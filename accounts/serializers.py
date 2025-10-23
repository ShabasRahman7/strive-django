from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'line1', 'line2', 'city', 'state', 'pin_code',
            'address_type', 'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_blocked', 'profile_image', 'addresses',
            'password', 'confirm_password', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'name', 'password', 'confirm_password']
        extra_kwargs = {
            'username': {'required': False}
        }

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError("Passwords don't match")
        
        # Handle name field - split into first_name and last_name
        name = attrs.get('name')
        if name:
            name_parts = name.strip().split(' ', 1)
            attrs['first_name'] = name_parts[0]
            attrs['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            attrs.pop('name', None)
        
        # Set username to email if not provided
        if not attrs.get('username'):
            attrs['username'] = attrs.get('email')
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            if user.is_blocked:
                raise serializers.ValidationError('User account is blocked')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password')


class UserProfileSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'profile_image', 'addresses', 'date_joined'
        ]
        read_only_fields = ['id', 'role', 'date_joined']


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for admin user management"""
    addresses = AddressSerializer(many=True, read_only=True)
    isBlocked = serializers.BooleanField(source='is_blocked')
    firstName = serializers.CharField(source='first_name')
    lastName = serializers.CharField(source='last_name')
    profileImage = serializers.URLField(source='profile_image')
    dateJoined = serializers.DateTimeField(source='date_joined')
    lastLogin = serializers.DateTimeField(source='last_login')
    isActive = serializers.BooleanField(source='is_active')
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'firstName', 'lastName',
            'role', 'isBlocked', 'profileImage', 'addresses',
            'dateJoined', 'lastLogin', 'isActive'
        ]
        read_only_fields = ['id', 'dateJoined', 'lastLogin']


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin user updates"""
    isBlocked = serializers.BooleanField(source='is_blocked', required=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'is_blocked', 'isBlocked', 'profile_image', 'is_active'
        ]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Serializer for admin user creation"""
    password = serializers.CharField(write_only=True, min_length=6, required=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'role', 'password', 'is_blocked', 'profile_image'
        ]
    
    def create(self, validated_data):
        # For admin-created users, don't require password
        password = validated_data.pop('password', None)
        
        # Set admin-added flag and make user inactive initially
        validated_data['is_admin_added'] = True
        validated_data['is_active'] = False  # User will be activated after password setup
        
        user = User.objects.create_user(**validated_data)
        
        # Only set password if provided (for testing purposes)
        if password:
            user.set_password(password)
            user.is_active = True  # If password provided, activate immediately
        else:
            # Set a temporary unusable password for admin-created users
            user.set_unusable_password()
        
        user.save()
        return user


class PasswordSetupSerializer(serializers.Serializer):
    """Serializer for password setup"""
    token = serializers.CharField()
    password = serializers.CharField(min_length=6)
    confirm_password = serializers.CharField()
    
    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError("Passwords don't match")
        return attrs


