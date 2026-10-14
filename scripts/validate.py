#!/usr/bin/env python3
"""Check generated feeds/pages against the manifest and require 24 1000px JPEGs."""
import argparse
import csv
import json
from html.parser import HTMLParser
from pathlib import Path
import struct
from urllib.parse import urlsplit, unquote

from build import ROOT, FEED_FIELDS, load_catalog


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.in_body = False
        self.in_script = False
        self.script_type = None
        self.metadata = {}
        self.duplicate_metadata = []
        self.metadata_outside_head = []
        self.jsonld = []
        self.script_buffer = ""
        self.links = []
        self.ids = set()
        self.visible = []
        self.forms = []
        self.purchase_disabled = False
        self.unexpected_scripts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.in_head = True
        if tag == "body":
            self.in_body = True
        if tag == "meta" and "property" in attrs:
            key = attrs["property"]
            if key in self.metadata:
                self.duplicate_metadata.append(key)
            if not self.in_head:
                self.metadata_outside_head.append(key)
            self.metadata[key] = attrs.get("content", "")
        if tag == "script":
            self.in_script = True
            self.script_type = attrs.get("type")
            self.script_buffer = ""
            if self.script_type != "application/ld+json" or "src" in attrs:
                self.unexpected_scripts.append(attrs)
            if not self.in_head:
                self.metadata_outside_head.append("JSON-LD")
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in ("form", "input", "textarea", "select", "iframe", "object", "embed"):
            self.forms.append(tag)
        if tag == "button" and "purchase-button" in attrs.get("class", "").split():
            self.purchase_disabled = "disabled" in attrs
        for key in ("src", "href"):
            if key in attrs:
                self.links.append(attrs[key])

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if tag == "body":
            self.in_body = False
        if tag == "script":
            if self.script_type == "application/ld+json":
                self.jsonld.append(json.loads(self.script_buffer))
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.script_buffer += data
        elif self.in_body and data.strip():
            self.visible.append(data.strip())


def jpeg_size(path):
    """Read JPEG SOF dimensions without an image-library dependency."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("not a complete JPEG (SOI/EOI markers missing)")
    pos = 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise ValueError("malformed JPEG marker")
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            break
        length = struct.unpack(">H", data[pos:pos + 2])[0]
        if length < 2 or pos + length > len(data):
            raise ValueError("malformed JPEG segment length")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if length < 8:
                raise ValueError("malformed JPEG size segment")
            height, width = struct.unpack(">HH", data[pos + 3:pos + 7])
            return width, height
        pos += length
    raise ValueError("JPEG has no readable size segment")


def validate(catalog, output, skip_images=False):
    errors = []
    base = catalog["base_url"]
    products = catalog["products"]
    expected_images = {f"images/{p['sku']}-{suffix}.jpg" for p in products for suffix in ("main", "lifestyle-1", "lifestyle-2")}

    def check(condition, message):
        if not condition:
            errors.append(message)

    for filename, id_field in (("meta_catalog.csv", "id"), ("tiktok_catalog.csv", "sku_id")):
        with (output / filename).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            check(reader.fieldnames == [id_field, *FEED_FIELDS], f"{filename}: incorrect header")
            rows = list(reader)
        check(len(rows) == 8, f"{filename}: expected exactly eight rows")
        check({r.get(id_field) for r in rows} == {p['sku'] for p in products}, f"{filename}: SKU set differs from manifest")
        by_sku = {r.get(id_field): r for r in rows}
        for product in products:
            sku = product["sku"]
            expected = {
                id_field: sku, "title": product["title"], "description": product["description"],
                "availability": "in stock", "condition": "new", "price": "29.00 USD",
                "link": base + f"products/{sku}.html", "image_link": base + f"images/{sku}-main.jpg",
                "additional_image_link": ",".join(base + f"images/{sku}-lifestyle-{i}.jpg" for i in (1, 2)),
                "brand": catalog["brand"], "google_product_category": product["google_product_category"],
            }
            check(by_sku.get(sku) == expected, f"{filename}: {sku} differs from manifest or URL contract")

    pages = {}
    for name in ["index.html", *[f"products/{p['sku']}.html" for p in products]]:
        path = output / name
        check(path.is_file(), f"missing page: {name}")
        if not path.is_file():
            continue
        page = Page(path.read_text(encoding="utf-8"))
        pages[name] = page
        check(not page.duplicate_metadata, f"{name}: duplicate metadata {page.duplicate_metadata}")
        check(not page.metadata_outside_head, f"{name}: metadata is outside head")
        check(not page.forms and not page.unexpected_scripts, f"{name}: unexpected form, embedded content, or executable script")
    check(len(list((output / "products").glob("*.html"))) == 8, "product directory must contain exactly eight pages")
    for product in products:
        sku = product["sku"]
        name = f"products/{sku}.html"
        page = pages.get(name)
        if not page:
            continue
        url = base + name
        images = [base + f"images/{sku}-{suffix}.jpg" for suffix in ("main", "lifestyle-1", "lifestyle-2")]
        expected_metadata = {
            "og:title": product["title"], "og:description": product["description"], "og:url": url,
            "og:image": images[0], "og:type": "product", "product:brand": catalog["brand"],
            "product:availability": "in stock", "product:condition": "new", "product:price:amount": "29.00",
            "product:price:currency": "USD", "product:retailer_item_id": sku,
        }
        for key, value in expected_metadata.items():
            check(page.metadata.get(key) == value, f"{name}: {key} differs from manifest")
        check(len(page.jsonld) == 1, f"{name}: expected one JSON-LD product")
        if len(page.jsonld) == 1:
            actual = page.jsonld[0]
            expected_schema = {
                "@context": "https://schema.org", "@type": "Product", "sku": sku, "name": product["title"],
                "description": product["description"], "image": images, "brand": {"@type": "Brand", "name": catalog["brand"]},
                "url": url, "offers": {"@type": "Offer", "url": url, "priceCurrency": "USD", "price": "29.00",
                                      "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition"},
            }
            check(actual == expected_schema, f"{name}: JSON-LD differs from manifest")
        visible = " ".join(page.visible)
        for text in (product["title"], product["description"], "$29.00 USD", "In stock", "New"):
            check(text in visible, f"{name}: missing visible product value: {text}")
        check(page.purchase_disabled, f"{name}: purchasing must be disabled")
        for image in images:
            relative_image = "../" + image.removeprefix(base)
            check(relative_image in page.links, f"{name}: missing gallery image {relative_image}")

    # Resolve every local link/resource against the artifact directory, not the repo root.
    for name, page in pages.items():
        for link in page.links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                if not link.startswith(base):
                    errors.append(f"{name}: unexpected external link or resource: {link}")
                    continue
                relative = urlsplit(link[len(base):]).path or "index.html"
                target = output / unquote(relative)
            else:
                if parts.path.startswith("/"):
                    errors.append(f"{name}: root-relative path would break a project-site base: {link}")
                    continue
                target = output / name if not parts.path else (output / name).parent / unquote(parts.path)
            target = target.resolve()
            check(target.is_relative_to(output.resolve()), f"{name}: link escapes public directory: {link}")
            if not target.is_relative_to(output.resolve()):
                continue
            relative = target.relative_to(output.resolve()).as_posix()
            if not (skip_images and relative in expected_images):
                check(target.is_file(), f"{name}: broken local link: {link}")
            if parts.fragment and relative in pages:
                check(parts.fragment in pages[relative].ids, f"{name}: missing anchor target: {link}")

    if not skip_images:
        for name in sorted(expected_images):
            path = output / name
            if not path.is_file():
                errors.append(f"missing image: {name}")
                continue
            try:
                size = jpeg_size(path)
                check(size == (1000, 1000), f"{name}: expected 1000x1000 JPEG, got {size}")
            except ValueError as error:
                errors.append(f"{name}: {error}")
    if errors:
        raise ValueError("\n".join(errors))
    images_note = "image checks SKIPPED (not release ready)" if skip_images else "24 JPEG headers verified at 1000x1000"
    print(f"PASS: 8 SKUs, both CSVs, 9 pages, product metadata, visible values, and local links; {images_note}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "catalog.json")
    parser.add_argument("--base-url", help="Must match the base URL used by the build")
    parser.add_argument("--output", type=Path, default=ROOT / "public")
    parser.add_argument("--skip-images", action="store_true", help="Development only: explicitly skip missing/dimension checks")
    args = parser.parse_args()
    try:
        validate(load_catalog(args.manifest, args.base_url), args.output, args.skip_images)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Validation failed:\n{error}\n")


if __name__ == "__main__":
    main()
