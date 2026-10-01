import urllib.error

import pytest

from migration.mysql.d1_usage import fetch_accounts, summarize


def test_summarize_adds_rows_per_database_and_total():
    groups = [
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 10}},
        {"dimensions": {"databaseId": "b"}, "sum": {"rowsRead": 5}},
        {"dimensions": {"databaseId": "a"}, "sum": {"rowsRead": 1}},
    ]
    total, per = summarize(groups, {"a": "kbo-stats"})
    assert total == 16
    assert per == {"kbo-stats": 11, "b": 5}


def test_fetch_accounts_refreshes_login_once_when_token_expired():
    calls = []
    tokens = iter(["old", "new"])
    refreshed = []

    def call(tok, url, body=None):
        calls.append((tok, url))
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
        return {"result": [{"id": "acc"}]}

    tok, accounts = fetch_accounts(read=lambda: next(tokens),
                                   refresh=lambda: refreshed.append(1),
                                   call=call)
    assert len(refreshed) == 1
    assert tok == "new"
    assert accounts == [{"id": "acc"}]
    assert [c[0] for c in calls] == ["old", "new"]


def test_fetch_accounts_does_not_refresh_on_other_errors():
    refreshed = []

    def call(tok, url, body=None):
        raise urllib.error.HTTPError(url, 500, "Server Error", hdrs=None, fp=None)

    with pytest.raises(urllib.error.HTTPError):
        fetch_accounts(read=lambda: "tok",
                       refresh=lambda: refreshed.append(1),
                       call=call)
    assert refreshed == []
