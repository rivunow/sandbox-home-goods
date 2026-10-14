"""Encode the generated assets as the specified 1000px catalog JPEGs.

Generation and background extraction are performed with the built-in image tool.
This step only frames, resizes, flattens alpha to white, and encodes final files.
Requires Pillow for this optional asset preparation step, not for site builds.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def export(record, source_dir, output_dir):
    source = source_dir / record["source_filename"]
    with Image.open(source) as opened:
        opened.load()
        if record["kind"] == "main":
            if opened.mode != "RGBA" or opened.getchannel("A").getextrema()[0] != 0:
                raise ValueError(f"{source.name}: primary needs a real transparent cutout")
            image = opened.copy()
            alpha = image.getchannel("A")
            bbox = alpha.point(lambda value: 255 if value > 128 else 0).getbbox()
            if not bbox:
                raise ValueError(f"{source.name}: empty product cutout")
            image = image.crop(bbox)
            image.thumbnail((750, 750), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (1000, 1000), "white")
            canvas.paste(image, ((1000-image.width)//2, (1000-image.height)//2), image)
        else:
            if opened.width != opened.height:
                raise ValueError(f"{source.name}: lifestyle source must be square")
            canvas = opened.convert("RGB").resize((1000, 1000), Image.Resampling.LANCZOS)
        output = output_dir / f'{record["sku"]}-{record["kind"]}.jpg'
        canvas.save(output, "JPEG", quality=95, subsampling=0)
    with Image.open(output) as checked:
        checked.load()
        if checked.format != "JPEG" or checked.size != (1000, 1000):
            raise ValueError(f"{output.name}: invalid final format or size")
        if record["kind"] == "main":
            for box in ((0, 0, 1000, 100), (0, 900, 1000, 1000),
                        (0, 0, 100, 1000), (900, 0, 1000, 1000)):
                if checked.crop(box).getextrema() != ((255, 255),)*3:
                    raise ValueError(f"{output.name}: outer background is not pure white")
    return {"sku": record["sku"], "kind": record["kind"],
            "filename": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "bytes": output.stat().st_size, "size": [1000, 1000]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--records", type=Path, default=Path("asset-generation.json"))
    args = parser.parse_args()
    records = json.loads(args.records.read_text())["assets"]
    output_dir = Path("public/images")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [export(record, args.source_dir, output_dir) for record in records]
    print(json.dumps({"exported": len(results), "images": results}, indent=2))


if __name__ == "__main__":
    main()
