import json

import pytest

from migration.mysql import conn


def _write(tmp_path, data):
    p = tmp_path / "mysql.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_settings_reads_all_required_keys(tmp_path):
    p = _write(tmp_path, {"host": "1.2.3.4", "port": 3306, "database": "bstats",
                          "user": "u", "password_file": "pw.txt", "ssl_ca": "ca.pem"})
    s = conn.load_settings(p)
    assert s["host"] == "1.2.3.4"
    assert s["port"] == 3306


def test_load_settings_names_missing_keys(tmp_path):
    p = _write(tmp_path, {"host": "1.2.3.4"})
    with pytest.raises(ValueError, match="ssl_ca"):
        conn.load_settings(p)
