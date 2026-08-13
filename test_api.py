import pandas as pd
from fastapi.testclient import TestClient

import backend.main as main

client = TestClient(main.app)


def fake_data():
    idx = pd.date_range('2025-01-01', periods=80, freq='h', tz='UTC')
    rows = pd.DataFrame({
        'timestamp': idx,
        'open': [100 + (i % 8) * 0.1 for i in range(80)],
        'high': [101 + (i % 8) * 0.1 for i in range(80)],
        'low': [99 + (i % 8) * 0.1 for i in range(80)],
        'close': [100.2 + (i % 8) * 0.1 for i in range(80)],
        'volume': [1000.0] * 80,
    })
    return {'1d': rows.copy(), '4h': rows.copy(), '1h': rows.copy()}


def test_health():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_analyse_contract(monkeypatch):
    monkeypatch.setattr(main, 'load_market_data', lambda *args, **kwargs: fake_data())
    r = client.post('/api/analyse', json={'provider':'crypto','symbol':'BTC/USDT','exchange':'binance'})
    assert r.status_code == 200
    body = r.json()
    assert set(body['charts']) == {'1d','4h','1h'}
    assert 'levels' in body
