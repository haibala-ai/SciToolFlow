import gzip, json, tempfile, unittest
from pathlib import Path
from src.utils.io import read_jsonl


class CompressedReferenceTests(unittest.TestCase):
    def test_plain_and_gzip_jsonl_are_identical(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            text = (
                "\n".join(
                    map(
                        json.dumps,
                        [{"id": "t1", "value": "研究"}, {"id": "t2", "value": [1, 2]}],
                    )
                )
                + "\n\n"
            )
            (root / "rows.jsonl").write_text(text)
            with gzip.open(root / "rows.jsonl.gz", "wt", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(
                read_jsonl(root / "rows.jsonl"), read_jsonl(root / "rows.jsonl.gz")
            )
