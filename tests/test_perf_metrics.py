import json

def test_perf_metrics_endpoint(client):
    # Trigger a couple of requests (home + metrics)
    r1 = client.get('/')
    assert r1.status_code in (200,302)
    r2 = client.get('/__perf_metrics')
    assert r2.status_code == 200
    data = json.loads(r2.data.decode('utf-8'))
    assert 'requests' in data
    assert 'routes' in data
    # Ensure at least one route recorded (home or redirect target)
    assert data['requests'] >= 1
