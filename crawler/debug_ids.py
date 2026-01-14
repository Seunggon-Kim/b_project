from download import get_game_ids
import datetime

start_date = datetime.date(2025, 6, 28)
end_date = datetime.date(2025, 6, 28)

try:
    game_ids = get_game_ids(start_date, end_date)
    print(f"Game IDs for 2025-06-28: {game_ids}")
except Exception as e:
    print(f"Error getting game IDs: {e}")
