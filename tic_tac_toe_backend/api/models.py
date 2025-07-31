from django.db import models
from django.contrib.auth.models import AbstractUser

# PUBLIC_INTERFACE
class User(AbstractUser):
    """
    Custom user model
    Extends AbstractUser, adds easy extensibility for future profile fields.
    """
    # Optionally, add display_name/profile_pic fields in future
    pass

# PUBLIC_INTERFACE
class Game(models.Model):
    """
    Stores a Tic Tac Toe game between two users.
    """
    STATUS_CHOICES = [
        ('WAITING', "Waiting for second player"),
        ('IN_PROGRESS', "Game in progress"),
        ('FINISHED', "Game finished")
    ]
    player_x = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_x')
    player_o = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_o', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='games_won', null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    board_state = models.CharField(max_length=9, default=' ' * 9)  # serialized flat string, e.g. 'XXO OX   '

    def __str__(self):
        return f"Game {self.pk}: {self.player_x.username} vs {self.player_o.username if self.player_o else '...'}"

# PUBLIC_INTERFACE
class Move(models.Model):
    """
    Stores a move for a game.
    """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='moves')
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    position = models.IntegerField()  # 0-8 for 3x3 board
    symbol = models.CharField(max_length=1)  # 'X' or 'O'
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Move ({self.symbol}) at {self.position} in {self.game_id}"
