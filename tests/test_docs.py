"""The documents link to files that exist, and the figures match the numbers they draw."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"


def load_figures():
    spec = importlib.util.spec_from_file_location("figures", ASSETS / "figures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentTests(unittest.TestCase):
    def test_relative_links_and_images_resolve(self):
        pattern = re.compile(r'\]\(([^)\s]+)\)|(?:src|srcset|href)="([^"]+)"')
        for doc in ROOT.rglob("*.md"):
            if ".preview" in doc.parts:
                continue
            for match in pattern.finditer(doc.read_text(encoding="utf-8")):
                target = (match.group(1) or match.group(2)).split("#")[0]
                if not target or re.match(r"^[a-z]+:", target):
                    continue
                with self.subTest(doc=doc.relative_to(ROOT).as_posix(), target=target):
                    self.assertTrue((doc.parent / target).exists())

    def test_sealed_figure_matches_real_traffic_table(self):
        figures = load_figures()
        table = {}
        for line in (ROOT / "eval" / "REAL_TRAFFIC.md").read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 6 and cells[0] in {h for h, _, _ in figures.SEALED}:
                table[cells[0]] = (cells[2], cells[5])   # v4, v5 from base
        self.assertEqual(len(table), 10)
        for head, v4, v5 in figures.SEALED:
            self.assertEqual(table[head], (figures.pct(v4), figures.pct(v5)), head)

    def test_committed_svgs_are_regenerated(self):
        figures = load_figures()
        with tempfile.TemporaryDirectory() as tmp:
            figures.OUT = Path(tmp)
            figures.main()
            for fresh in Path(tmp).glob("*.svg"):
                with self.subTest(svg=fresh.name):
                    self.assertEqual(fresh.read_bytes(), (ASSETS / fresh.name).read_bytes())


if __name__ == "__main__":
    unittest.main()
