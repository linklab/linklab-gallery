"""Build a complete daily gallery without writing images to Git."""

import argparse
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image

DEFAULT_ALBUM_TOKEN = "D2Pv3-0ipoABnYhZQG6aSWSHTWQCAEQARogjZAL_TI0PSTTlxf2IRQiTpJDG8lVGLC73-hmIuX38xE"
PHOTO_COUNT = 4
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024


def request_bytes(url: str, payload: dict[str, Any] | None = None) -> bytes:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(result) > MAX_DOWNLOAD_BYTES:
                raise ValueError("Download exceeds the size limit")
            return result
        except urllib.error.HTTPError as error:
            if error.code == 330 and payload is not None:
                with error:
                    return error.read(MAX_DOWNLOAD_BYTES)
            if error.code != 429 and error.code < 500:
                raise
            error.close()
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2**attempt)
    raise RuntimeError("Request failed")


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(request_bytes(url, payload))


def get_album(token: str) -> tuple[dict[str, Any], str]:
    stream = post_json(f"https://sharedstreams.icloud.com/{token}/sharedstreams/webstream", {"streamCtag": None})
    host = stream.get("X-Apple-MMe-Host", "sharedstreams.icloud.com")
    if host != "sharedstreams.icloud.com":
        if not host.endswith(".icloud.com") or "/" in host:
            raise ValueError("Unexpected iCloud album host")
        stream = post_json(f"https://{host}/{token}/sharedstreams/webstream", {"streamCtag": None})
    return stream, host


def select_photos(stream: dict[str, Any], day: date) -> list[dict[str, Any]]:
    photos = {
        item["photoGuid"]: item
        for item in stream["photos"]
        if item.get("derivatives") and all(key.isdigit() for key in item["derivatives"])
    }
    if len(photos) < PHOTO_COUNT:
        raise ValueError(f"Need {PHOTO_COUNT} different photos; found {len(photos)}")
    return random.Random(day.isoformat()).sample([photos[key] for key in sorted(photos)], PHOTO_COUNT)


def verify_jpeg(data: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        # iCloud also serves HDR JPEGs with an embedded MPO gain map.
        if image.format not in ("JPEG", "MPO"):
            raise ValueError("Expected a JPEG image")
        image.verify()
    with Image.open(BytesIO(data)) as image:
        image.load()
        return image.size


def build_gallery(output: Path, day: date, token: str) -> None:
    stream, host = get_album(token)
    photos = select_photos(stream, day)
    assets = post_json(
        f"https://{host}/{token}/sharedstreams/webasseturls",
        {"photoGuids": [photo["photoGuid"] for photo in photos]},
    )["items"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="gallery-", dir=output.parent) as temporary:
        staging = Path(temporary)
        images = []
        for index, photo in enumerate(photos, start=1):
            derivatives = photo["derivatives"]
            checksum = derivatives[max(derivatives, key=int)]["checksum"]
            asset = assets[checksum]
            data = request_bytes(f"https://{asset['url_location']}{asset['url_path']}")
            width, height = verify_jpeg(data)
            filename = f"{index}.jpg"
            (staging / filename).write_bytes(data)
            images.append(
                {"file": filename, "sha256": hashlib.sha256(data).hexdigest(), "width": width, "height": height}
            )
        manifest = {"date": day.isoformat(), "images": images}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        for file in staging.iterdir():
            file.replace(output / file.name)
    print(f"Gallery ready: {day.isoformat()}, {len(images)} verified JPEG images")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("site"))
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Seoul")).date())
    args = parser.parse_args()
    token = os.environ.get("ICLOUD_ALBUM_TOKEN") or DEFAULT_ALBUM_TOKEN
    build_gallery(args.output, args.date, token)


if __name__ == "__main__":
    main()
