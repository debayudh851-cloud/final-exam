import secrets
from datetime import timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def validate(self, attrs):
        try:
            validate_password(attrs['password'], User(username=attrs['username'], email=attrs['email']))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(**validated_data, role=User.Role.HR)
            code = f'{secrets.randbelow(1000000):06d}'
            user.otp_hash = make_password(code)
            user.otp_expires_at = timezone.now() + timedelta(minutes=10)
            user.save(update_fields=['otp_hash', 'otp_expires_at'])
            send_mail('Verify your recruitment portal account', f'Your verification code is {code}. It expires in 10 minutes.',
                      None, [user.email], fail_silently=False)
        return user


class VerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(r'^\d{6}$')

    def verify(self):
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=self.validated_data['email']).first()
            if (not user or user.email_verified or not user.otp_hash or not user.otp_expires_at
                    or user.otp_expires_at < timezone.now() or user.otp_attempts >= 5):
                return False
            if not check_password(self.validated_data['code'], user.otp_hash):
                user.otp_attempts += 1
                user.save(update_fields=['otp_attempts'])
                return False
            user.email_verified = True
            user.otp_hash = ''
            user.otp_expires_at = None
            user.save(update_fields=['email_verified', 'otp_hash', 'otp_expires_at'])
            return True


class VerifiedTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.verified:
            raise serializers.ValidationError('Verify your email before signing in.')
        data['role'] = self.user.role
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
