"""Queue one image for local embedding and vector indexing."""

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
    parser = argparse.ArgumentParser(description="Queue one image for indexing.")
    parser.add_argument("image", type=Path, help="Image path")
    parser.add_argument("--id", default=None, help="Image id; defaults to the file stem")
    parser.add_argument("--api", default="http://127.0.0.1:4568", help="API base URL")
    args = parser.parse_args()

    image_path = args.image.resolve()
    image_id = args.id or image_path.stem
    payload = {
        "id": image_id,
        "base64": encode_image(image_path),
        "url": str(image_path),
    }
    result = post_json(f"{args.api.rstrip('/')}/api/images/ingest", payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
