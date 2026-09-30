from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

# Header do client gửi là input không tin cậy: chỉ nhận đúng format, còn lại sinh ID mới
# để chuỗi tùy ý (dài, chứa PII) không đi vào log/trace.
REQUEST_ID_PATTERN = re.compile(r"req-[0-9a-f]{8}")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_contextvars()

        incoming = request.headers.get("x-request-id", "")
        correlation_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else f"req-{uuid.uuid4().hex[:8]}"
        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(int((time.perf_counter() - start) * 1000))
        return response
