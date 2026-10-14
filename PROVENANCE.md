# Synthetic catalog provenance

Studio SHG Eight is a fictional brand. All eight products, descriptions, prices, and stock states were created for this catalog experiment. They do not represent inventory, suppliers, sales, or endorsement by a real brand. No real logo, product photograph, shipping claim, or customer data is used.

Source: the approved eight-SKU specification, captured in `catalog.json`. Product text and generated metadata derive from that file. Category strings were checked against [Google's official taxonomy](https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt) on 2026-10-14.

## Image records

All 32 final photographs were produced using the built-in `image_gen` tool on 2026-10-14. The actual prompts, generated source filenames, reference source filenames, and final asset mapping are recorded in `asset-generation.json`. Original generated PNGs are retained in the tool's generated-images directory; the final JPEGs are checked into `public/images/`.

For each SKU, retain the same object across one studio image and three styled images. Final filenames are `<sku>-main.jpg`, `<sku>-lifestyle-1.jpg`, `<sku>-lifestyle-2.jpg`, and `<sku>-lifestyle-3.jpg`, at 1000 × 1000 pixels. Images must have no real brand marks, logos, price overlays, or other text overlays.

For each primary, the image tool extracted a transparent product cutout from the generated studio photograph. `scripts/export_images.py` frames the existing cutout at 75% of the final canvas's longest dimension, flattens alpha onto pure white, and encodes a 1000 × 1000 RGB JPEG at quality 95. The initial two lifestyle images reference the same original studio product; the third references the final primary JPEG. All lifestyle images are resized and JPEG-encoded without background changes. Exporting assets requires Pillow; building and validating the site use Python's standard library.

A fresh independent reviewer inspected the initial 24 final images and decoded every JPEG. The review found consistent product types, colors, materials and key details, no visible logos/text/watermarks, and complete centered primaries. All eight primary images had zero nonwhite pixels in their outer 100-pixel border. Local contact sheets and export hashes are retained in ignored `output/` files. This asset review establishes visible consistency and file integrity, not platform acceptance or eligibility.

The requested third styled image was added for each SKU without replacing any original asset. A fresh independent reviewer inspected all eight new JPEGs individually and alongside the primary references, decoded each as 1000 × 1000 RGB JPEG, and verified the four-image page/schema mapping and three additional URLs in both feeds. The review found no visible text, logos, watermarks, or material product identity changes. All 24 original JPEGs remained byte-identical. This additional image review does not establish platform ingestion or creative eligibility.
