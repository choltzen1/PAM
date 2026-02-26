import os

from data import oracle_client


def test_build_dsn_uses_explicit_env(monkeypatch):
    monkeypatch.setenv('ORACLE_DSN', 'EXPLICIT_DSN')
    dsn = oracle_client._build_dsn()
    assert dsn == 'EXPLICIT_DSN'


def test_build_dsn_from_parts(monkeypatch):
    monkeypatch.delenv('ORACLE_DSN', raising=False)
    monkeypatch.setenv('ORACLE_HOST', 'example.host')
    monkeypatch.setenv('ORACLE_SERVICE', 'svc')
    monkeypatch.setenv('ORACLE_PORT', '1521')
    dsn = oracle_client._build_dsn()
    assert 'example.host' in dsn
    assert 'svc' in dsn
