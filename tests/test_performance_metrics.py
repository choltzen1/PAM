import json, time

# NOTE: Assumes /__perf_metrics route is registered in app (see app.py)

def test_metrics_accumulate_basic(client):
    # Prime: ensure clean snapshot start (no reset yet, so rely on increasing counts)
    client.get('/')  # home
    client.get('/')  # home again
    client.get('/admin')  # maybe redirect/200 depending on auth logic

    mresp = client.get('/__perf_metrics')
    assert mresp.status_code == 200
    data = json.loads(mresp.data.decode('utf-8'))
    assert 'routes' in data and 'requests' in data
    assert data['requests'] >= 3
    # Ensure at least home endpoint recorded
    # endpoint names are namespaced (core.home) from blueprint
    # fallback to path if endpoint not resolved
    found = any(k.endswith('home') or k == '/' for k in data['routes'].keys())
    assert found, f"Expected home route key present, got: {list(data['routes'].keys())}"


def test_route_latency_fields_present(client):
    # Hit a route with some artificial slight delay (if needed we can just rely on natural timing)
    client.get('/')
    mresp = client.get('/__perf_metrics')
    data = json.loads(mresp.data.decode('utf-8'))
    # Find any route record and validate structure
    assert data['routes'], 'No route metrics recorded'
    sample = next(iter(data['routes'].values()))
    assert {'count','avg_ms','max_ms'} <= set(sample.keys())
    assert sample['count'] >= 1
    assert sample['max_ms'] >= sample['avg_ms']


def test_metrics_after_more_requests_increase(client):
    before = json.loads(client.get('/__perf_metrics').data.decode('utf-8'))
    before_requests = before['requests']
    # Make more calls
    for _ in range(5):
        client.get('/')
    after = json.loads(client.get('/__perf_metrics').data.decode('utf-8'))
    assert after['requests'] >= before_requests + 5

