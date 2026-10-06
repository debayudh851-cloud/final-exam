from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path, include
from django.shortcuts import redirect
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from accounts import views as accounts
from recruitment import views, api

router = DefaultRouter()
router.register('candidates', api.CandidateViewSet, basename='api-candidate')
router.register('roles', api.RoleViewSet, basename='role')
router.register('interview-slots', api.SlotViewSet, basename='slot')

urlpatterns = [
    path('', lambda request: redirect('dashboard')),
    path('admin/', admin.site.urls),
    path('accounts/login/', accounts.login_page, name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('accounts/register/', accounts.register_page, name='register'),
    path('accounts/verify/', accounts.verify_page, name='verify'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/candidates/', views.CandidateList.as_view(), name='candidate-list'),
    path('dashboard/candidates/add/', views.candidate_edit, name='candidate-add'),
    path('dashboard/candidates/<int:pk>/', views.CandidateDetail.as_view(), name='candidate-detail'),
    path('dashboard/candidates/<int:pk>/edit/', views.candidate_edit, name='candidate-edit'),
    path('dashboard/candidates/<int:pk>/delete/', views.CandidateDelete.as_view(), name='candidate-delete'),
    path('dashboard/candidates/<int:pk>/status/', views.status_edit, name='candidate-status'),
    path('dashboard/candidates/<int:pk>/rescreen/', views.rescreen, name='candidate-rescreen'),
    path('dashboard/candidates/<int:pk>/assign/', views.assign_interview, name='candidate-assign'),
    path('dashboard/candidates/<int:pk>/media/<str:kind>/', views.candidate_media, name='candidate-media'),
    path('dashboard/upload/', views.upload, name='upload'),
    path('dashboard/batches/<int:pk>/', views.batch_detail, name='batch-detail'),
    path('dashboard/batches/<int:pk>/status/', views.batch_status, name='batch-status'),
    path('dashboard/batches/<int:pk>/retry/', views.retry_batch, name='batch-retry'),
    path('dashboard/batches/<int:pk>/download/<str:kind>/', views.batch_download, name='batch-download'),
    path('dashboard/ajax/email/', views.email_check, name='email-check'),
    path('dashboard/ajax/slots/', views.role_slots, name='role-slots'),
    path('dashboard/interviews/', views.interviews, name='interviews'),
    path('dashboard/interviews/<int:pk>/feedback/', views.feedback, name='feedback'),
    path('dashboard/json/candidates/', views.candidate_json, name='candidate-json-list'),
    path('dashboard/json/candidates/<int:pk>/', views.candidate_json, name='candidate-json'),
    path('api/auth/register/', accounts.RegisterAPI.as_view()),
    path('api/auth/verify/', accounts.VerifyAPI.as_view()),
    path('api/auth/login/', accounts.LoginAPI.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/auth/logout/', accounts.LogoutAPI.as_view()),
    path('api/batches/upload/', api.BatchUploadAPI.as_view()),
    path('api/batches/<int:pk>/status/', api.BatchStatusAPI.as_view()),
    path('api/batches/<int:pk>/download/<str:kind>/', api.BatchDownloadAPI.as_view()),
    path('api/screening-results/', api.ScreeningListAPI.as_view()),
    path('api/interview-slots/create/', api.SlotCreateAPI.as_view()),
    path('api/interviews/assign/', api.AssignAPI.as_view()),
    path('api/interview-feedback/', api.FeedbackAPI.as_view()),
    path('api/screening/predict/', api.PredictAPI.as_view()),
    path('api/screening/nlp/', api.NLPAPI.as_view()),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include(router.urls)),
]
