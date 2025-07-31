from django.urls import re_path
from .consumers import GameConsumer

# PUBLIC_INTERFACE
# WebSocket URLs for real-time game updates
websocket_urlpatterns = [
    re_path(r'ws/game/(?P<game_id>\d+)/$', GameConsumer.as_asgi(), name='ws-game'),
]
