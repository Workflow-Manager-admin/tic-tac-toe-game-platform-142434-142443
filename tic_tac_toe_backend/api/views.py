from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status, viewsets, generics, mixins
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from .models import Game, Move
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    GameSerializer,
    GameCreateSerializer,
    MoveSerializer,
)

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

User = get_user_model()

# PUBLIC_INTERFACE
@api_view(['GET'])
def health(request):
    """Health endpoint for server status check."""
    return Response({"message": "Server is up!"})

# PUBLIC_INTERFACE
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user.
    ---
    Request body:
        username: str
        password: str
    Response:
        User profile or error.
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# PUBLIC_INTERFACE
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Login a user and return JWT tokens.
    ---
    Request body:
        username: str
        password: str
    Response:
        Access/Refresh tokens and user profile.
    """
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({"detail": "Invalid credentials"}, status=401)
    refresh = RefreshToken.for_user(user)
    return Response({
        "user": UserProfileSerializer(user).data,
        "refresh": str(refresh),
        "access": str(refresh.access_token)
    }, status=200)

# PUBLIC_INTERFACE
class ProfileView(APIView):
    """
    Get the authenticated user's profile and game stats.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        wins = Game.objects.filter(winner=user).count()
        total_games = Game.objects.filter(player_x=user).count() + Game.objects.filter(player_o=user).count()
        data = UserProfileSerializer(user).data
        data['total_games'] = total_games
        data['games_won'] = wins
        return Response(data)

# PUBLIC_INTERFACE
class GameViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.ListModelMixin):
    """
    Game endpoints - create/start, list/join, get board, get history
    """
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return GameCreateSerializer
        return GameSerializer

    def list(self, request):
        """
        List all games the user is part of or available to join (status: WAITING or IN_PROGRESS).
        """
        user = request.user
        games = Game.objects.filter(
            (Q(player_x=user) | Q(player_o=user)) |
            (Q(status='WAITING') & ~Q(player_x=user))
        ).order_by('-start_time').distinct()
        serializer = self.get_serializer(games, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request):
        """
        Start a new game or join a waiting game.
        If a game with status 'WAITING' exists, join it as player O.
        Else, create a new game as player X.
        """
        user = request.user
        waiting_game = Game.objects.filter(status="WAITING").exclude(player_x=user).first()
        if waiting_game:
            waiting_game.player_o = user
            waiting_game.status = "IN_PROGRESS"
            waiting_game.save()
            return Response(GameSerializer(waiting_game).data, status=200)

        new_game = Game.objects.create(player_x=user)
        return Response(GameSerializer(new_game).data, status=201)

    def retrieve(self, request, pk=None):
        """
        Get game board, moves, and status for given game id.
        """
        game = get_object_or_404(Game, pk=pk)
        serializer = self.get_serializer(game)
        return Response(serializer.data)

# PUBLIC_INTERFACE
class MoveView(APIView):
    """
    Make a move in a game.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Make a move as current user in specified game.
        Expects:
            position: int (0-8)
        Enforces turn order, symbol assignment, win/draw conditions.
        """
        user = request.user
        game = get_object_or_404(Game, pk=pk)

        if game.status != 'IN_PROGRESS':
            return Response({"detail": "Game is not available for moves."}, status=400)

        moves = list(game.moves.all().order_by('timestamp'))
        board = list(game.board_state)
        # Determine whose turn
        is_x = (len(moves) % 2 == 0)
        expected_player = game.player_x if is_x else game.player_o
        symbol = 'X' if is_x else 'O'

        if expected_player != user:
            return Response({'detail': "Not your turn."}, status=403)

        pos = int(request.data.get('position', -1))
        if pos < 0 or pos > 8 or board[pos] != ' ':
            return Response({'detail': "Invalid move."}, status=400)

        # Make move
        board[pos] = symbol
        game.board_state = ''.join(board)
        move = Move.objects.create(game=game, player=user, position=pos, symbol=symbol)
        # Check for win/draw
        result = self.check_winner(board)
        if result:
            game.status = 'FINISHED'
            if result == 'draw':
                game.winner = None
            else:
                game.winner = user
            game.end_time = timezone.now()
        game.save()

        # WebSocket notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'game_{game.id}', 
            {
                "type": "game_update",
                "content": {
                    "type": "move",
                    "game_id": game.id,
                    "board": game.board_state,
                    "move": MoveSerializer(move).data,
                    "winner": game.winner.username if game.winner else None,
                    "status": game.status,
                }
            }
        )
        return Response(GameSerializer(game).data, status=200)

    # PUBLIC_INTERFACE
    def check_winner(self, board):
        """
        Check for Tic Tac Toe winner or draw.
        Returns "draw", "X", "O", or None.
        """
        win_cond = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
                    (0, 3, 6), (1, 4, 7), (2, 5, 8),
                    (0, 4, 8), (2, 4, 6)]
        for a, b, c in win_cond:
            if board[a] != ' ' and board[a] == board[b] == board[c]:
                return board[a]
        if ' ' not in board:
            return 'draw'
        return None

# PUBLIC_INTERFACE
class GameHistoryView(generics.ListAPIView):
    """
    Get game history for the current user.
    """
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Game.objects.filter(Q(player_x=user) | Q(player_o=user)).order_by('-start_time')

# --- WebSocket routing (ASGI setup is in config/asgi.py and separate routing file, usually at root) ---

