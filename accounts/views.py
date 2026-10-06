from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema
from .serializers import RegisterSerializer, VerifySerializer, VerifiedTokenSerializer, LogoutSerializer
from .throttles import LocalAnonThrottle


class VerificationThrottle(LocalAnonThrottle):
    scope = 'verification'


class RegisterAPI(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [VerificationThrottle]

    def perform_create(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc


class VerifyAPI(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [VerificationThrottle]
    serializer_class = VerifySerializer

    @extend_schema(request=VerifySerializer, responses={200: dict, 400: dict})
    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.verify():
            return Response({'detail': 'Invalid, expired, or exhausted verification code.'}, status=400)
        return Response({'detail': 'Email verified. You can sign in.'})


class LoginAPI(TokenObtainPairView):
    serializer_class = VerifiedTokenSerializer


class LogoutAPI(APIView):
    serializer_class = LogoutSerializer

    @extend_schema(request=LogoutSerializer, responses={200: dict, 400: dict})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            if str(token['user_id']) != str(request.user.pk):
                return Response({'detail': 'Refresh token belongs to another account.'}, status=400)
            token.blacklist()
        except TokenError:
            return Response({'detail': 'Invalid refresh token.'}, status=400)
        return Response({'detail': 'Refresh token revoked. Access token expires after 15 minutes.'})


def login_page(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if user.verified:
            login(request, user)
            return redirect('dashboard')
        form.add_error(None, 'Verify your email before signing in.')
    return render(request, 'accounts/login.html', {'form': form})


def register_page(request):
    errors = {}
    if request.method == 'POST':
        serializer = RegisterSerializer(data=request.POST)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
        except (ValidationError, DjangoValidationError) as exc:
            errors = getattr(exc, 'detail', None) or getattr(exc, 'messages', None)
        else:
            messages.success(request, 'Account created. Use the email code to verify it. In local console mode, the code appears in the server terminal.')
            return redirect('verify')
    return render(request, 'accounts/register.html', {'errors': errors})


def verify_page(request):
    if request.method == 'POST':
        serializer = VerifySerializer(data=request.POST)
        if serializer.is_valid() and serializer.verify():
            messages.success(request, 'Email verified. Please sign in.')
            return redirect('login')
        messages.error(request, 'Invalid, expired, or exhausted verification code.')
    return render(request, 'accounts/verify.html')
