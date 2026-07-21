"""Fetch device list from tzone_server getUserDeviceWithPaginationHandler."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# DeviceFilterType.All in server types
FILTER_ALL = 7
TZ_SUCCESS = 0


def decode_user_id_from_token(token: str) -> str:
    """Decode JWT payload (no verify) and return user id."""
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("invalid JWT token format")
    payload = parts[1]
    padding = "=" * ((4 - len(payload) % 4) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload + padding))
    user_id = data.get("id")
    if not user_id:
        raise ValueError("JWT payload has no id field")
    return str(user_id)


def fetch_all_devices(
    api_url: str,
    token: str,
    user_id: Optional[str] = None,
    pagesize: int = 100,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Page through POST /v1/device/userpagination/:uid until all devices are loaded.

    api_url should be the API root, e.g. http://localhost:9000/api
    """
    api_root = api_url.rstrip("/")
    uid = user_id or decode_user_id_from_token(token)
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "accesstoken": token,
    }

    devices: List[Dict[str, Any]] = []
    page = 1
    total: Optional[int] = None

    while True:
        url = f"{api_root}/v1/device/userpagination/{uid}"
        body = {
            "page": page,
            "pagesize": pagesize,
            "keyword": "",
            "filter": FILTER_ALL,
            "keyChanged": page == 1,
            "total": total or 0,
        }
        logging.info(f"fetching devices page={page} pagesize={pagesize}")
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)
        if resp.status_code == 403:
            raise PermissionError(
                "access token rejected (403). "
                "server.token must be a web login accesstoken "
                "(browser localStorage 'accesstoken' after login), "
                "not an API key. It must include client_type=WEB."
            )
        resp.raise_for_status()
        payload = resp.json()

        error_code = payload.get("error_code")
        if error_code != TZ_SUCCESS:
            raise RuntimeError(
                f"device API error: code={error_code} meta={payload.get('meta')}"
            )

        page_obj = payload.get("object") or {}
        batch = page_obj.get("data") or []
        total = page_obj.get("total", total)
        has_next = page_obj.get("has_next", 0)

        devices.extend(batch)
        logging.info(
            f"page {page}: got {len(batch)} devices "
            f"(accumulated={len(devices)}, total={total})"
        )

        if not batch or not has_next:
            break
        page += 1

    return devices


def save_devices_json(devices: List[Dict[str, Any]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)
    logging.info(f"saved {len(devices)} devices to {out}")
    return out


def load_devices_json(path: str | Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"devices file must be a JSON array: {path}")
    return data
