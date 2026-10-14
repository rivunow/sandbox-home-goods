# Studio SHG Eight

A browse-only storefront and two catalog feeds for eight fictional home goods. Purchasing is disabled. The site contains no checkout, tracking code, pixel, contact form, or claimed shipping policy.

`catalog.json` is the source for every product page, Open Graph field, JSON-LD Product, and catalog row. Shared attributes are `29.00 USD`, `in stock`, `new`, and `Studio SHG Eight`. Stock and prices are synthetic; no real inventory or transaction exists. See [PROVENANCE.md](PROVENANCE.md) for asset provenance.

## Build and check

Building and validating the checked-in site requires Python 3.9 or newer, with no third-party packages. Optional re-exporting of generated PNGs requires Pillow:

```sh
python3 scripts/export_images.py --source-dir /path/to/generated-images
```

`asset-generation.json` records the actual image prompts and source filenames. Exported JPEGs are already included, so this step is unnecessary for ordinary builds or deployment.

```sh
python3 scripts/build.py
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

Before image generation is finished, `python3 scripts/validate.py --skip-images` checks pages and feeds. That option explicitly skips image readiness and must not be used to approve a release.

The manifest's `image_suffixes` lists the gallery and feed images in order. The strict check currently requires these four 1000 × 1000 JPEG files for each of `mug`, `tote`, `board`, `pillow`, `bottle`, `vase`, `organizer`, and `coaster`:

```text
public/images/<sku>-main.jpg
public/images/<sku>-lifestyle-1.jpg
public/images/<sku>-lifestyle-2.jpg
public/images/<sku>-lifestyle-3.jpg
```

The validator reads JPEG markers and size headers. Visual consistency and full image decoding are separate checks. The builder preserves `public/images/` when rebuilding.

To preview locally:

```sh
python3 -m http.server 8000 --directory public
```

Open `http://localhost:8000/`. Page navigation and image/CSS paths are relative, so local preview works. Feed, canonical, and metadata URLs still refer to the configured public base.

## Publish with GitHub Pages

The intended public repository is `rivunow/sandbox-home-goods`; its site base is [https://rivunow.github.io/sandbox-home-goods/](https://rivunow.github.io/sandbox-home-goods/). Enable **Settings → Pages → Build and deployment → Source → GitHub Actions**. The `github-pages` environment must allow deployment from the selected branch.

After committing the source and all 32 images, manually run **Actions → Publish storefront → Run workflow**. The workflow runs the contract tests, rebuilds and strictly validates the site, uploads only `public/`, and deploys the artifact. It never publishes on push. Its deployment job has `pages: write` and `id-token: write`; the build has `contents: read`. Action references are pinned to the verified major-version SHAs.

A different host or repository path must be passed to both commands:

```sh
python3 scripts/build.py --base-url https://example.com/collection/
python3 scripts/validate.py --base-url https://example.com/collection/
```

The workflow exposes the same `base_url` input. Use the actual site base; do not leave the planned URL after a hosting change. The builder normalizes a missing final slash and rejects non-HTTPS, credentials, query/fragment, or ambiguous path segments. Rebuilding updates every absolute product/image URL.

## Catalog endpoints

- [Meta CSV](https://rivunow.github.io/sandbox-home-goods/meta_catalog.csv)
- [TikTok CSV](https://rivunow.github.io/sandbox-home-goods/tiktok_catalog.csv)

Meta uses `id`; TikTok uses `sku_id`. Both include `title`, `description`, `availability`, `condition`, `price`, `link`, `image_link`, `additional_image_link`, `brand`, and `google_product_category`. The three extra image URLs occupy one comma-separated CSV cell, quoted by Python's CSV writer. Categories use strings verified against [Google's official taxonomy](https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt), rather than arbitrary numeric IDs.

Product pages live at `products/<sku>.html`. Each has four images, visible attributes, product Open Graph metadata in the document head, and one matching JSON-LD Product with an Offer.

These files do not establish platform acceptance. Record actual import results and capability gates separately. Advertiser setup and platform operations are outside this build.
