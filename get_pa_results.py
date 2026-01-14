import sqlite3
import json

def get_pa_results():
    conn = sqlite3.connect('database/kbo_stats.db')
    cursor = conn.cursor()
    cursor.execute("SELECT pa_result, COUNT(*) FROM play_by_play GROUP BY pa_result")
    results = cursor.fetchall()
    conn.close()
    
    with open('pa_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print("PA results saved to pa_results.json")

if __name__ == "__main__":
    get_pa_results()
