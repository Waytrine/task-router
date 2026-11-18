"""Dataset integrity checks. Standard library only; no model, network or GPU."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE_KEYS = {"message", "recent_context", "reference_text", "attachments", "candidate_executors"}
TRAIN_FILES = ["train", "train_v2", "train_v3", "train_v4"]
EVAL_FILES = ["validation", "calibration", "test", "calibration_v4", "blind_test_v4"]


def rows(name):
    return [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


class DatasetTest(unittest.TestCase):
    def test_published_bytes_match_manifests(self):
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
        rounds = json.loads((DATA / "rounds.json").read_text(encoding="utf-8"))
        expected = dict(manifest["sha256"]) | {path: info["sha256"] for path, info in rounds["files"].items()}
        self.assertEqual(len(expected), 10)
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)

    def test_split_sizes(self):
        sizes = {name: len(rows(name)) for name in ["train", "validation", "calibration", "test", "all", *TRAIN_FILES[1:], "calibration_v4", "blind_test_v4"]}
        self.assertEqual(sizes, {"train": 240, "validation": 60, "calibration": 40, "test": 60, "all": 400,
                                 "train_v2": 400, "train_v3": 520, "train_v4": 720,
                                 "calibration_v4": 60, "blind_test_v4": 20})

    def test_rows_follow_the_ten_head_schema(self):
        questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
        self.assertEqual(len(questions), 10)
        for name in ["all", *TRAIN_FILES[1:], "calibration_v4", "blind_test_v4"]:
            for row in rows(name):
                with self.subTest(file=name, id=row["id"]):
                    self.assertEqual(set(row["state"]), STATE_KEYS)
                    self.assertEqual(row["questions"], questions)
                    self.assertEqual(set(row["expected"]), set(questions))
                    for head, label in row["expected"].items():
                        self.assertIn(label, questions[head]["criteria"])
                    for attachment in row["state"]["attachments"]:
                        # Attachment metadata only: never file contents.
                        self.assertLessEqual(set(attachment), {"kind", "name", "mime_type"})

    def test_every_scenario_has_both_languages(self):
        for name in ["all", *TRAIN_FILES[1:], "calibration_v4", "blind_test_v4"]:
            groups = {}
            for row in rows(name):
                groups.setdefault(row["group_id"], set()).add(row["language"])
            with self.subTest(file=name):
                self.assertTrue(all(languages == {"zh", "en"} for languages in groups.values()))

    def test_no_family_group_or_message_crosses_from_training_into_evaluation(self):
        for train_name in TRAIN_FILES:
            train = rows(train_name)
            for eval_name in EVAL_FILES:
                evaluation = rows(eval_name)
                for key in ("family_id", "group_id"):
                    with self.subTest(train=train_name, evaluation=eval_name, key=key):
                        self.assertFalse({r[key] for r in train} & {r[key] for r in evaluation})
                with self.subTest(train=train_name, evaluation=eval_name, key="message"):
                    self.assertFalse({r["state"]["message"] for r in train} & {r["state"]["message"] for r in evaluation})

    def test_provenance_declares_synthetic_data(self):
        provenance = json.loads((DATA / "provenance.json").read_text(encoding="utf-8"))
        self.assertFalse(provenance["private_logs_used"])
        self.assertIn("synthetic", provenance["origin"].lower())

    def test_rebuild_from_source_matches_manifest(self):
        with tempfile.TemporaryDirectory(prefix="task-router-rebuild-") as directory:
            out = Path(directory) / "build"
            subprocess.run([sys.executable, "-B", str(ROOT / "training" / "build_dataset.py"), "--out", str(out)],
                           check=True, capture_output=True, timeout=600)
            rebuilt = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rebuilt, json.loads((DATA / "manifest.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
