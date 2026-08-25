"""Search the local image index with one query image."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from urllib import request


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search local image vectors.")
    parser.add_argument("image", type=Path, help="Query image path")
    parser.add_argument("--api", default="http://127.0.0.1:4568", help="API base URL")
    parser.add_argument("--top-k", type=int, default=20, help="Number of matches to return")
    parser.add_argument("--threshold", type=float, default=None, help="Optional score threshold")
    args = parser.parse_args()

    payload = {
        "base64": encode_image(args.image),
        "top_k": args.top_k,
        "threshold": args.threshold,
    }
    result = post_json(f"{args.api.rstrip('/')}/api/search", payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
