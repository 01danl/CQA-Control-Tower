"""Organizer GET client. Never log URLs, response bodies or HTTP exception strings."""

import math
import time
from collections import Counter
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import unquote_plus, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.contracts import SourceConversation
from app.errors import ServiceError
from app.privacy import silence_transport_logs


def group_url(secret_url: str, group_id: str) -> str:
    try:
        parts = urlsplit(secret_url)
        _ = parts.port
    except ValueError:
        raise ServiceError(
            503, "DATASET_NOT_CONFIGURED", "Configure a valid HTTPS dataset endpoint"
        ) from None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ServiceError(
            503, "DATASET_NOT_CONFIGURED", "Configure a valid HTTPS dataset endpoint"
        )
    # Preserve untouched fields byte-for-byte, including Azure signature encoding.
    fields = parts.query.split("&") if parts.query else []
    result: list[str] = []
    replaced = False
    for field in fields:
        if unquote_plus(field.split("=", 1)[0]) == "group_id":
            if not replaced:
                result.append(urlencode({"group_id": group_id}))
                replaced = True
        else:
            result.append(field)
    if not replaced:
        result.append(urlencode({"group_id": group_id}))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(result), parts.fragment))


@dataclass(frozen=True)
class Dataset:
    records: list[SourceConversation]
    language_counts: dict[str, int]


def parse_dataset(payload: object) -> Dataset:
    if not isinstance(payload, dict) or payload.get("isSuccess") is not True:
        raise ServiceError(502, "DATASET_REJECTED", "Dataset did not report success")
    if any(payload.get(key) for key in ("error", "errors", "errorMessage")):
        raise ServiceError(502, "DATASET_REJECTED", "Dataset reported an error")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ServiceError(502, "DATASET_FORMAT", "Dataset must include data.records")
    total = data.get("total_records", payload.get("total_records"))
    if type(total) is not int or total != len(data["records"]):
        raise ServiceError(502, "DATASET_COUNT", "Dataset total_records does not match records")
    if "total_records" in payload and payload["total_records"] != total:
        raise ServiceError(502, "DATASET_COUNT", "Conflicting dataset record counts")
    if len(data["records"]) > 10000:
        raise ServiceError(502, "DATASET_TOO_LARGE", "Dataset exceeds the import limit")
    try:
        records = [SourceConversation.model_validate(item) for item in data["records"]]
    except (ValidationError, ValueError, TypeError):
        raise ServiceError(502, "DATASET_RECORD", "Dataset contains an invalid record") from None
    if len({r.conversation_id for r in records}) != len(records):
        raise ServiceError(502, "DATASET_DUPLICATE", "Dataset contains duplicate conversation IDs")
    return Dataset(records, dict(Counter(record.language for record in records)))


def retry_delay(response: httpx.Response | None, attempt: int, backoff: float) -> float:
    if response is not None:
        header = response.headers.get("Retry-After", "")
        try:
            delay = float(header)
            if math.isfinite(delay) and delay >= 0:
                return delay
        except ValueError:
            try:
                date = parsedate_to_datetime(header)
                if date.tzinfo is not None:
                    return max(0, date.timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    return min(5, backoff * (2**attempt))


class DatasetClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.transport = transport
        self.sleep = sleep

    def fetch(self, group_id: str) -> Dataset:
        silence_transport_logs()
        secret = self.settings.cqa_dataset_url
        if not secret or not secret.get_secret_value():
            raise ServiceError(503, "DATASET_NOT_CONFIGURED", "Dataset endpoint is not configured")
        url = group_url(secret.get_secret_value(), group_id)
        with httpx.Client(
            timeout=self.settings.dataset_timeout_seconds,
            transport=self.transport,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for attempt in range(self.settings.http_retries + 1):
                response = None
                try:
                    response = client.get(url)
                except httpx.HTTPError:
                    if attempt == self.settings.http_retries:
                        raise ServiceError(
                            502, "DATASET_UNAVAILABLE", "Dataset request failed"
                        ) from None
                else:
                    if response.status_code == 200:
                        try:
                            return parse_dataset(response.json())
                        except ValueError:
                            raise ServiceError(
                                502, "DATASET_JSON", "Dataset returned malformed JSON"
                            ) from None
                    if response.status_code != 429 and response.status_code < 500:
                        raise ServiceError(502, "DATASET_HTTP", "Dataset rejected the request")
                    if attempt == self.settings.http_retries:
                        code = (
                            "DATASET_RATE_LIMITED"
                            if response.status_code == 429
                            else "DATASET_UNAVAILABLE"
                        )
                        raise ServiceError(
                            503 if response.status_code == 429 else 502,
                            code,
                            "Dataset temporarily unavailable",
                        )
                delay = retry_delay(response, attempt, self.settings.retry_backoff_seconds)
                if delay > self.settings.max_retry_delay_seconds:
                    code = (
                        "DATASET_RATE_LIMITED"
                        if response is not None and response.status_code == 429
                        else "DATASET_UNAVAILABLE"
                    )
                    raise ServiceError(
                        503, code, "Dataset requested a later retry; retry the import later"
                    )
                self.sleep(delay)
        raise AssertionError("Unreachable retry loop")
