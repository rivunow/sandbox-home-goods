"""A small integration contract for the generated, externally consumed catalog."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.metadata = {}
        self.jsonld_text = ""
        self.in_jsonld = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and "property" in attrs:
            self.metadata[attrs["property"]] = attrs.get("content")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_jsonld = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_jsonld = False

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld_text += data


class CatalogContract(unittest.TestCase):
    def run_build(self, output, *extra):
        self.assertTrue((ROOT / "scripts/build.py").exists(), "The catalog builder is not implemented yet")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build.py"), "--output", str(output), *extra], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_csv_and_product_metadata_agree_at_custom_project_path(self):
        base = "https://example.test/nested/collection/"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            self.run_build(output, "--base-url", base.rstrip("/"))
            with (output / "meta_catalog.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            with (output / "tiktok_catalog.csv").open(newline="") as f:
                tiktok = list(csv.DictReader(f))
            self.assertEqual({r["id"] for r in rows}, {"mug", "tote", "board", "pillow", "bottle", "vase", "organizer", "coaster"})
            self.assertEqual(len(rows), 8)
            for row, other in zip(rows, tiktok):
                self.assertEqual(row["id"], other.pop("sku_id"))
                self.assertEqual({k: v for k, v in row.items() if k != "id"}, other)
                self.assertEqual(row["price"], "29.00 USD")
                self.assertEqual(row["link"], base + "products/" + row["id"] + ".html")
                self.assertTrue(row["image_link"].startswith(base + "images/"))
                self.assertEqual(len(row["additional_image_link"].split(",")), 2)
                page = Page((output / "products" / (row["id"] + ".html")).read_text())
                product = json.loads(page.jsonld_text)
                self.assertEqual(page.metadata["og:url"], row["link"])
                self.assertEqual(page.metadata["og:title"], row["title"])
                self.assertEqual(page.metadata["og:description"], row["description"])
                self.assertEqual(page.metadata["og:image"], row["image_link"])
                self.assertEqual(page.metadata["product:retailer_item_id"], row["id"])
                self.assertEqual(product["sku"], row["id"])
                self.assertEqual(product["image"], [row["image_link"], *row["additional_image_link"].split(",")])
                self.assertEqual(product["offers"]["price"], "29.00")
                self.assertEqual(product["offers"]["availability"], "https://schema.org/InStock")
                self.assertEqual(product["offers"]["url"], row["link"])

    def test_csv_preserves_comma_quotes_and_escaped_html_content(self):
        self.assertTrue((ROOT / "catalog.json").exists(), "The source manifest is not implemented yet")
        manifest = json.loads((ROOT / "catalog.json").read_text())
        description = 'Matte ivory mug, with a "rounded" handle & a quiet finish.'
        manifest["products"][0]["description"] = description
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "catalog.json"
            source.write_text(json.dumps(manifest))
            self.run_build(tmp / "output", "--manifest", str(source))
            with (tmp / "output/meta_catalog.csv").open(newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["description"], description)
            page = Page((tmp / "output/products/mug.html").read_text())
            self.assertEqual(page.metadata["og:description"], description)
            self.assertEqual(json.loads(page.jsonld_text)["description"], description)

    def test_base_url_rejects_query_fragment_and_non_https(self):
        self.assertTrue((ROOT / "scripts/build.py").exists(), "The catalog builder is not implemented yet")
        with tempfile.TemporaryDirectory() as tmp:
            for url in ("http://example.test/", "https://example.test/?q=1", "https://example.test/#hash", "https://example.test/a/../b/"):
                result = subprocess.run([sys.executable, str(ROOT / "scripts/build.py"), "--output", tmp, "--base-url", url], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, url)
                self.assertIn("base URL", result.stderr)


if __name__ == "__main__":
    unittest.main()
