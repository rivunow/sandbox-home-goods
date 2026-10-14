"""Release validation must reject drift and must not silently skip images."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseValidation(unittest.TestCase):
    def test_validation_catches_metadata_drift_and_requires_assets(self):
        self.assertTrue((ROOT / "scripts/validate.py").exists(), "Release validator is not implemented yet")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            subprocess.run([sys.executable, str(ROOT / "scripts/build.py"), "--output", tmp], check=True, capture_output=True)
            command = [sys.executable, str(ROOT / "scripts/validate.py"), "--output", tmp]
            without_images = subprocess.run([*command, "--skip-images"], capture_output=True, text=True)
            self.assertEqual(without_images.returncode, 0, without_images.stderr)
            strict = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(strict.returncode, 0)
            self.assertIn("missing image", strict.stderr.lower())
            path = output / "products/mug.html"
            path.write_text(path.read_text().replace('property="product:price:amount" content="29.00"', 'property="product:price:amount" content="30.00"'))
            drift = subprocess.run([*command, "--skip-images"], capture_output=True, text=True)
            self.assertNotEqual(drift.returncode, 0)
            self.assertIn("product:price:amount", drift.stderr)


if __name__ == "__main__":
    unittest.main()
