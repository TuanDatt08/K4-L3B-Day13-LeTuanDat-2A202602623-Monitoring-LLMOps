from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PATTERN = re.compile(r"req-[0-9a-f]{8}")


def test_valid_request_id_is_propagated() -> None:
    response = client.get("/health", headers={"x-request-id": "req-abcdef12"})
    assert response.headers["x-request-id"] == "req-abcdef12"
    assert int(response.headers["x-response-time-ms"]) >= 0


def test_missing_or_invalid_request_id_is_replaced() -> None:
    for headers in ({}, {"x-request-id": "student@vinuni.edu.vn"}, {"x-request-id": "req-" + "a" * 500}):
        response = client.get("/health", headers=headers)
        assert PATTERN.fullmatch(response.headers["x-request-id"])
