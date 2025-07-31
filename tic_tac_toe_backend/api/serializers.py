from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Game, Move

User = get_user_model()

# PUBLIC_INTERFACE
class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'], password=validated_data['password']
        )
        return user

# PUBLIC_INTERFACE
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Public user profile serializer.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'date_joined']

# PUBLIC_INTERFACE
class MoveSerializer(serializers.ModelSerializer):
    """
    Serializer for game moves.
    """
    class Meta:
        model = Move
        fields = ['id', 'game', 'player', 'position', 'symbol', 'timestamp']
        read_only_fields = ['game', 'player', 'symbol', 'timestamp']

# PUBLIC_INTERFACE
class GameSerializer(serializers.ModelSerializer):
    """
    Serializer for game, including current board state and moves.
    """
    player_x = UserProfileSerializer(read_only=True)
    player_o = UserProfileSerializer(read_only=True)
    moves = MoveSerializer(many=True, read_only=True)
    
    class Meta:
        model = Game
        fields = [
            'id', 
            'player_x', 'player_o',
            'status', 'winner',
            'start_time', 'end_time',
            'board_state',
            'moves'
        ]

# PUBLIC_INTERFACE
class GameCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for game creation (start game/join game)
    """
    class Meta:
        model = Game
        fields = ['id', 'player_x', 'player_o']
