from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path, allowed_statuses",
    [
        ("/", {200, 302, 401, 403}),
        ("/__perf_metrics", {200}),
        ("/admin", {200, 302, 401, 403}),
        ("/admin/ui-refactor", {200, 302, 401, 403}),
        ("/api/generate_next_promo_code", {200, 302, 400, 401, 403}),
    ],
)
def test_key_routes_do_not_500(client, path: str, allowed_statuses: set[int]) -> None:
    resp = client.get(path)
    assert resp.status_code in allowed_statuses, f"{path} returned {resp.status_code}"


def test_offers_route_removed(client, app) -> None:
    resp = client.get("/offers")
    assert resp.status_code == 404

    rules = [r.rule for r in app.url_map.iter_rules()]
    assert "/offers" not in rules
