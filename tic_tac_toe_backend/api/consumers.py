import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

User = get_user_model()

# PUBLIC_INTERFACE
class GameConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time game updates.
    Handles group communication for each game room.
    """

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.room_group_name = f'game_{self.game_id}'
        # Accept connection and add to the game group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name, self.channel_name
        )

    # Receive message from WebSocket (e.g., making move—not recommended, but supported)
    async def receive(self, text_data):
        # For this task: only broadcast moves from backend, don't process in websocket
        pass

    async def game_update(self, event):
        """
        Called by server backend to send an update (e.g., a move was made, board changed).
        """
        await self.send(text_data=json.dumps(event["content"]))
