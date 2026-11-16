"""Verify the migration preserves the historical chart data."""
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("charts", ROOT / "docs/make-charts.py")
CHARTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHARTS)


class ChartTests(unittest.TestCase):
    def test_historical_labels_and_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            CHARTS.generate(output)
            files = list(output.rglob("*.svg"))
            self.assertEqual(len(files), 10)
            for file in files:
                generated = ET.parse(file).getroot()
                original = ET.parse(ROOT / "docs/images" / file.relative_to(output)).getroot()
                tags = "{http://www.w3.org/2000/svg}text"
                self.assertEqual([item.text for item in generated.iter(tags)],
                                 [item.text for item in original.iter(tags)], file.name)


if __name__ == "__main__":
    unittest.main()
