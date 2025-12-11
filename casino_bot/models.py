# models.py
# Game class definition for the casino bot

class Game:
    """Represents an active game session for a user."""
    
    def __init__(self, user_id: int, username: str, bet_amount: int, 
                 rounds: int, throw_count: int, game_type: str):
        """
        Initialize a new game session.
        
        Args:
            user_id: Telegram user ID
            username: User's display name
            bet_amount: Amount of stars bet
            rounds: Total number of rounds to play
            throw_count: Number of throws per round
            game_type: Type of game (dice, bowl, arrow, football, basket)
        """
        self.user_id = user_id
        self.username = username
        self.bet_amount = bet_amount
        self.total_rounds = rounds
        self.throw_count = throw_count
        self.game_type = game_type
        self.current_round = 0
        self.user_score = 0
        self.bot_score = 0
        self.user_results = []
        self.bot_results = []
        self.is_demo = False
        self.bot_first = False
        self.bot_rolled_this_round = False
        self.user_throws_this_round = 0
