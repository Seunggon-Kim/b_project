import json

import pymysql
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


def _capture(monkeypatch, tmp_path):
    seen = {}
    (tmp_path / "pw.txt").write_text("secret\n", encoding="ascii")
    monkeypatch.setattr(pymysql, "connect", lambda **kw: seen.update(kw) or object())
    return seen


def _settings(tmp_path, host, ssl_ca):
    return {"host": host, "port": 3306, "database": "bstats", "user": "u",
            "password_file": str(tmp_path / "pw.txt"), "ssl_ca": ssl_ca}


def test_settings_path_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BSTATS_MYSQL_SETTINGS", str(tmp_path / "p.json"))
    assert conn.settings_path() == tmp_path / "p.json"
    monkeypatch.delenv("BSTATS_MYSQL_SETTINGS")
    assert conn.settings_path().name == "mysql.json"
    assert conn.settings_path().parent.name == ".bstats"


def test_null_ssl_ca_on_localhost_connects_without_tls(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    conn.connect(_settings(tmp_path, "127.0.0.1", None))
    assert seen["host"] == "127.0.0.1"
    assert not any(k.startswith("ssl") for k in seen)
    assert seen["password"] == "secret"


def test_null_ssl_ca_on_public_host_is_refused(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="로컬 Auth Proxy"):
        conn.connect(_settings(tmp_path, "34.1.2.3", None))
    assert seen == {}


def test_tls_path_still_passes_ssl_args(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    conn.connect(_settings(tmp_path, "34.1.2.3", "ca.pem"))
    assert seen["ssl_ca"] == "ca.pem"
    assert seen["ssl_verify_cert"] is True
    assert seen["ssl_verify_identity"] is False


def test_load_settings_accepts_null_ssl_ca(tmp_path):
    p = _write(tmp_path, {"host": "127.0.0.1", "port": 3307, "database": "d",
                          "user": "u", "password_file": "pw", "ssl_ca": None})
    assert conn.load_settings(p)["ssl_ca"] is None


def test_proxy_path_passes_server_public_key(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    pem = tmp_path / "server_pub.pem"
    pem.write_bytes(b"-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n")
    s = _settings(tmp_path, "127.0.0.1", None)
    s["server_public_key_file"] = str(pem)
    conn.connect(s)
    assert seen["server_public_key"] == pem.read_bytes()
    assert not any(k.startswith("ssl") for k in seen)


def test_tls_path_never_passes_server_public_key(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    pem = tmp_path / "server_pub.pem"
    pem.write_bytes(b"KEY")
    s = _settings(tmp_path, "34.1.2.3", "ca.pem")
    s["server_public_key_file"] = str(pem)
    conn.connect(s)
    assert "server_public_key" not in seen
    s2 = _settings(tmp_path, "34.1.2.3", "ca.pem")
    conn.connect(s2)
    assert "server_public_key" not in seen


def test_proxy_path_without_key_file_omits_it(monkeypatch, tmp_path):
    seen = _capture(monkeypatch, tmp_path)
    conn.connect(_settings(tmp_path, "localhost", None))
    assert "server_public_key" not in seen
