import json
import unittest
import urllib.error
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from PIL import Image

from scripts.update_gallery import build_gallery, request_bytes, select_photos, verify_jpeg


def album(count: int = 12) -> dict[str, Any]:
    return {
        "photos": [{"photoGuid": str(index), "derivatives": {"1": {"checksum": str(index)}}} for index in range(count)]
    }


def jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 20), "blue").save(buffer, format="JPEG")
    return buffer.getvalue()


class GalleryTests(unittest.TestCase):
    def test_selection_uses_day_and_ignores_album_order(self) -> None:
        stream = album()
        today = select_photos(stream, date(2026, 10, 31))
        stream["photos"].reverse()
        self.assertEqual(today, select_photos(stream, date(2026, 10, 31)))
        self.assertNotEqual(today, select_photos(stream, date(2026, 11, 1)))
        self.assertEqual(len({photo["photoGuid"] for photo in today}), 4)

    def test_too_few_photos_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "different photos"):
            select_photos(album(3), date(2026, 10, 31))

    def test_corrupt_and_non_jpeg_images_are_rejected(self) -> None:
        self.assertEqual(verify_jpeg(jpeg()), (10, 20))
        for data in (b"<html>Error</html>", jpeg()[:100]):
            with self.subTest(data=data[:10]), self.assertRaises((OSError, ValueError)):
                verify_jpeg(data)

    def test_icloud_mpo_jpeg_is_supported(self) -> None:
        buffer = BytesIO()
        frame = Image.new("RGB", (10, 20), "blue")
        frame.save(buffer, format="MPO", save_all=True, append_images=[frame])
        self.assertEqual(verify_jpeg(buffer.getvalue()), (10, 20))

    def test_complete_output_and_failed_download_preserves_previous_output(self) -> None:
        assets = {str(index): {"url_location": "example.com", "url_path": f"/{index}"} for index in range(12)}
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "site"
            with (
                patch("scripts.update_gallery.get_album", return_value=(album(), "example.com")),
                patch("scripts.update_gallery.post_json", return_value={"items": assets}),
                patch("scripts.update_gallery.request_bytes", return_value=jpeg()),
            ):
                build_gallery(output, date(2026, 10, 31), "test")
            before = {file.name: file.read_bytes() for file in output.iterdir()}
            self.assertEqual(set(before), {"1.jpg", "2.jpg", "3.jpg", "4.jpg", "manifest.json"})
            self.assertEqual(json.loads(before["manifest.json"])["date"], "2026-10-31")
            with (
                patch("scripts.update_gallery.get_album", return_value=(album(), "example.com")),
                patch("scripts.update_gallery.post_json", return_value={"items": assets}),
                patch("scripts.update_gallery.request_bytes", side_effect=[jpeg(), ValueError("broken image")]),
                self.assertRaisesRegex(ValueError, "broken image"),
            ):
                build_gallery(output, date(2026, 11, 1), "test")
            self.assertEqual(before, {file.name: file.read_bytes() for file in output.iterdir()})

    def test_transient_network_failure_is_retried(self) -> None:
        with (
            patch(
                "scripts.update_gallery.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")
            ) as call,
            patch("scripts.update_gallery.time.sleep") as sleep,
            self.assertRaises(urllib.error.URLError),
        ):
            request_bytes("https://example.com")
        self.assertEqual(call.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_permanent_http_error_is_not_retried(self) -> None:
        error = urllib.error.HTTPError("https://example.com", 403, "Forbidden", None, None)
        with (
            patch("scripts.update_gallery.urllib.request.urlopen", side_effect=error) as call,
            patch("scripts.update_gallery.time.sleep") as sleep,
            self.assertRaises(urllib.error.HTTPError),
        ):
            request_bytes("https://example.com")
        self.assertEqual(call.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
