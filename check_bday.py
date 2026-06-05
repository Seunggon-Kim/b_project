
import sqlite3
conn = sqlite3.connect('database/kbo_stats.db')
val = conn.execute("SELECT birthday FROM players WHERE player_id = '69446'").fetchone()[0]
print(f"BIRTHDAY_VALUE: '{val}'")
print(f"BIRTHDAY_TYPE: {type(val)}")
conn.close()
