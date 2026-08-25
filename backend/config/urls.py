from django.urls import path
from monitor.views import dashboard, health, save_baseline

urlpatterns = [path('api/health/', health), path('api/dashboard/', dashboard), path('api/accounts/baseline/', save_baseline)]
