from migration.mysql.d1_usage import summarize


def test_summarize_adds_rows_per_database_and_total():
    groups = [
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 10}},
        {"dimensions": {"databaseId": "b"}, "sum": {"rowsRead": 5}},
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 1}},
    ]
    total, per = summarize(groups, {"a": "kbo-stats"})
    assert total == 16
    assert per == {"kbo-stats": 11, "b": 5}
