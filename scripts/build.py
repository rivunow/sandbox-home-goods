#!/usr/bin/env python3
"""Build the browse-only storefront and both catalogs using Python's stdlib."""
import argparse
import csv
import html
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SKUS = {"mug", "tote", "board", "pillow", "bottle", "vase", "organizer", "coaster"}
FEED_FIELDS = ["title", "description", "availability", "condition", "price", "link", "image_link", "additional_image_link", "brand", "google_product_category"]


def normalize_base_url(value):
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or "\\" in value or any(c.isspace() for c in value)):
        raise ValueError("base URL must be an absolute HTTPS URL without credentials, query, or fragment")
    path = unquote(parts.path)
    if any(part in (".", "..") for part in path.split("/")) or "//" in path:
        raise ValueError("base URL must not contain ambiguous path segments")
    if path != parts.path:
        raise ValueError("base URL must use an unescaped path")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/", "", ""))


def load_catalog(path, base_url=None):
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["base_url"] = normalize_base_url(base_url or catalog["base_url"])
    for field in ("brand", "currency", "price", "availability", "condition"):
        if not isinstance(catalog.get(field), str) or not catalog[field].strip():
            raise ValueError(f"manifest {field} must be a nonempty string")
    if (catalog["currency"], catalog["price"], catalog["availability"], catalog["condition"]) != ("USD", "29.00", "in stock", "new"):
        raise ValueError("this sandbox requires USD 29.00, in stock, and new for every item")
    suffixes = catalog["image_suffixes"]
    if (not isinstance(suffixes, list) or not suffixes or suffixes[0] != "main"
            or len(set(suffixes)) != len(suffixes)
            or any(not re.fullmatch(r"lifestyle-[1-9][0-9]*", suffix) for suffix in suffixes[1:])):
        raise ValueError("image_suffixes must start with main and contain unique lifestyle image suffixes")
    products = catalog["products"]
    if len(products) != 8 or {p["sku"] for p in products} != SKUS:
        raise ValueError("manifest must contain the eight approved SKUs exactly once")
    for product in products:
        if not re.fullmatch(r"[a-z]+", product["sku"]):
            raise ValueError("SKU must use lowercase letters")
        for field in ("title", "description", "material", "detail", "google_product_category"):
            if not isinstance(product.get(field), str) or not product[field].strip():
                raise ValueError(f"{product['sku']}: {field} must be a nonempty string")
    return catalog


def image_paths(catalog, product):
    return [f"images/{product['sku']}-{suffix}.jpg" for suffix in catalog["image_suffixes"]]


def product_url(catalog, product):
    return catalog["base_url"] + f"products/{product['sku']}.html"


def feed_row(catalog, product, id_field):
    images = [catalog["base_url"] + path for path in image_paths(catalog, product)]
    return {
        id_field: product["sku"], "title": product["title"], "description": product["description"],
        "availability": catalog["availability"], "condition": catalog["condition"],
        "price": f"{catalog['price']} {catalog['currency']}", "link": product_url(catalog, product),
        "image_link": images[0], "additional_image_link": ",".join(images[1:]),
        "brand": catalog["brand"], "google_product_category": product["google_product_category"],
    }


def escape(value):
    return html.escape(str(value), quote=True)


def head(catalog, title, description, url, image, product=None, prefix=""):
    metadata = {
        "og:title": title, "og:description": description, "og:url": url,
        "og:image": image, "og:type": "product" if product else "website", "og:site_name": catalog["brand"],
    }
    if product:
        metadata.update({"product:brand": catalog["brand"], "product:availability": catalog["availability"],
                         "product:condition": catalog["condition"], "product:price:amount": catalog["price"],
                         "product:price:currency": catalog["currency"], "product:retailer_item_id": product["sku"]})
    tags = "\n".join(f'  <meta property="{escape(key)}" content="{escape(value)}">' for key, value in metadata.items())
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | {escape(catalog['brand'])}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="theme-color" content="#254d3d">
  <link rel="canonical" href="{escape(url)}">
  <link rel="stylesheet" href="{prefix}styles.css">
{tags}
'''


def header(catalog, prefix=""):
    return f'''<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header wrap">
    <a class="wordmark" href="{prefix}index.html" aria-label="{escape(catalog['brand'])} home">Studio <span>SHG Eight</span></a>
    <nav aria-label="Main"><a href="{prefix}index.html#collection">The collection</a></nav>
  </header>
'''


def footer(catalog, prefix=""):
    return f'''  <footer class="site-footer wrap">
    <a class="footer-brand" href="{prefix}index.html">{escape(catalog['brand'])}</a>
    <p>Purchasing is currently unavailable.</p>
  </footer>
</body>
</html>
'''


def image_tag(path, alt, lazy=True):
    loading = 'loading="lazy"' if lazy else 'fetchpriority="high"'
    return f'<img src="{escape(path)}" alt="{escape(alt)}" width="1000" height="1000" {loading} decoding="async">'


def homepage(catalog):
    products = catalog["products"]
    mug = next(p for p in products if p["sku"] == "mug")
    cards = []
    for product in products:
        cards.append(f'''        <li>
          <a class="product-card" href="products/{product['sku']}.html">
            <div class="card-image">{image_tag(image_paths(catalog, product)[0], product['title'])}</div>
            <div class="card-caption"><h3>{escape(product['title'])}</h3><p>${escape(catalog['price'])} <span>USD</span></p></div>
            <p class="card-material">{escape(product['material'])}</p>
          </a>
        </li>''')
    description = "Eight simple objects in stoneware, linen, wood, glass, and more. Browse the Studio SHG Eight collection."
    return head(catalog, catalog["brand"], description, catalog["base_url"], catalog["base_url"] + image_paths(catalog, mug)[0]) + '</head>\n' + header(catalog) + f'''  <main id="main">
    <section class="hero wrap" aria-labelledby="hero-title">
      <div class="hero-copy">
        <h1 id="hero-title">A little room<br>for the everyday.</h1>
        <p>Eight simple objects. Quiet colors, familiar materials, and shapes that feel at home.</p>
        <a class="collection-link" href="#collection">Explore the collection</a>
      </div>
      <a class="hero-image" href="products/mug.html" aria-label="View the ivory stoneware mug">{image_tag(image_paths(catalog, mug)[0], 'Matte ivory stoneware mug with a large rounded handle', lazy=False)}</a>
    </section>
    <section id="collection" class="collection wrap" aria-labelledby="collection-title">
      <div class="section-heading"><h2 id="collection-title">The collection</h2><p>Objects for your everyday spaces.</p></div>
      <ul class="product-grid">
{chr(10).join(cards)}
      </ul>
    </section>
  </main>
''' + footer(catalog)


def product_page(catalog, product):
    images = image_paths(catalog, product)
    url = product_url(catalog, product)
    schema = {
        "@context": "https://schema.org", "@type": "Product", "sku": product["sku"],
        "name": product["title"], "description": product["description"],
        "image": [catalog["base_url"] + path for path in images],
        "brand": {"@type": "Brand", "name": catalog["brand"]}, "url": url,
        "offers": {"@type": "Offer", "url": url, "priceCurrency": catalog["currency"], "price": catalog["price"],
                   "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition"},
    }
    # Escape '<' so manifest text cannot terminate the inline JSON script element.
    jsonld = json.dumps(schema, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    labels = ["Studio view", *[f"Styled view {i}" for i in range(1, len(images))]]
    thumbnails = "\n".join(f'''          <a href="#view-{i + 1}" aria-label="View {label.lower()} of {escape(product['title'])}">{image_tag('../' + path, '', lazy=True)}<span>{label}</span></a>''' for i, (path, label) in enumerate(zip(images, labels)))
    figures = "\n".join(f'''        <figure id="view-{i + 1}" class="gallery-view">
          {image_tag('../' + path, product['title'] + (' — studio view' if i == 0 else f' — styled view {i}'), lazy=i > 0)}
          <figcaption>{('Studio view' if i == 0 else f'Styled view {i}')}</figcaption>
        </figure>''' for i, path in enumerate(images))
    return head(catalog, product["title"], product["description"], url, schema["image"][0], product, prefix="../") + f'''  <script type="application/ld+json">{jsonld}</script>
</head>
''' + header(catalog, "../") + f'''  <main id="main" class="wrap product-main">
    <a class="back-link" href="../index.html#collection">Back to the collection</a>
    <div class="product-layout">
      <section class="gallery" aria-label="{escape(product['title'])} images">
        <nav class="gallery-nav" aria-label="Choose a product image">
{thumbnails}
        </nav>
{figures}
      </section>
      <section class="product-information" aria-labelledby="product-title">
        <p class="product-brand">{escape(catalog['brand'])}</p>
        <h1 id="product-title">{escape(product['title'])}</h1>
        <p class="price">${escape(catalog['price'])} <span>{escape(catalog['currency'])}</span></p>
        <p class="stock"><span aria-hidden="true"></span>In stock</p>
        <p class="product-description">{escape(product['description'])}</p>
        <dl class="product-details">
          <div><dt>Material</dt><dd>{escape(product['material'])}</dd></div>
          <div><dt>Details</dt><dd>{escape(product['detail'])}</dd></div>
          <div><dt>Condition</dt><dd>New</dd></div>
        </dl>
        <button class="purchase-button" type="button" disabled aria-describedby="purchase-note">Purchasing unavailable</button>
        <p id="purchase-note" class="purchase-note">This collection is available to browse. Purchasing is currently unavailable.</p>
      </section>
    </div>
  </main>
''' + footer(catalog, "../")


def build(catalog, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "products").mkdir(exist_ok=True)
    (output / "index.html").write_text(homepage(catalog), encoding="utf-8")
    for product in catalog["products"]:
        (output / "products" / f"{product['sku']}.html").write_text(product_page(catalog, product), encoding="utf-8")
    shutil.copyfile(ROOT / "src/styles.css", output / "styles.css")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    for name, id_field in (("meta_catalog.csv", "id"), ("tiktok_catalog.csv", "sku_id")):
        with (output / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[id_field, *FEED_FIELDS], lineterminator="\n")
            writer.writeheader()
            writer.writerows(feed_row(catalog, product, id_field) for product in catalog["products"])
    print(f"Built 9 pages and 2 eight-row feeds in {output}; canonical base: {catalog['base_url']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "catalog.json")
    parser.add_argument("--base-url", help="Absolute HTTPS site base, including the repository path")
    parser.add_argument("--output", type=Path, default=ROOT / "public")
    args = parser.parse_args()
    try:
        build(load_catalog(args.manifest, args.base_url), args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Build failed: {error}\n")


if __name__ == "__main__":
    main()
