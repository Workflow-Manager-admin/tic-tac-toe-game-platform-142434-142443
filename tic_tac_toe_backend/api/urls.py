from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health, register, login, ProfileView,
    GameViewSet, MoveView, GameHistoryView
)

router = DefaultRouter()
router.register('games', GameViewSet, basename='game')

urlpatterns = [
    path('health/', health, name='Health'),
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('', include(router.urls)),
    path('games/<int:pk>/move/', MoveView.as_view(), name='make-move'),
    path('history/', GameHistoryView.as_view(), name='game-history'),
]
