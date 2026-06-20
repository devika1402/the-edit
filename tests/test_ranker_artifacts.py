from __future__ import annotations

import json
from pathlib import Path

from models.ranker import read_feature_list, write_feature_list


def test_feature_list_round_trip(tmp_path: Path) -> None:
    features = ["a", "b", "c"]
    write_feature_list(features, tmp_path)
    assert read_feature_list(tmp_path) == features
    assert json.loads((tmp_path / "feature_list.json").read_text())["features"] == features
