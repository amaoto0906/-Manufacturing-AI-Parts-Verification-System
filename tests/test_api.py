"""API のエンドツーエンドテスト（classic バックボーンで高速実行）。"""
import io

import pytest
from fastapi.testclient import TestClient

from partmatch.data.synth import generate_part_specs, render_part
from partmatch.service.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        # 小規模デモデータを生成・学習・索引構築
        r = c.post("/api/v1/generate-demo",
                   json={"n_parts": 12, "n_groups": 4, "imgs_per_part": 5,
                         "epochs": 15, "seed": 7})
        assert r.status_code == 200, r.text
        assert r.json()["ready"] is True
        yield c


def _png(spec, seed):
    buf = io.BytesIO()
    render_part(spec, seed=seed).save(buf, "PNG")
    buf.seek(0)
    return buf


def test_health_and_info(client):
    assert client.get("/health").json()["status"] == "ok"
    info = client.get("/api/v1/info").json()
    assert info["ready"] and info["index_size"] > 0


def test_inspect_correct_part(client):
    sp = generate_part_specs(12, 4, seed=7)[0]
    r = client.post("/api/v1/inspect",
                    files={"file": ("c.png", _png(sp, 9991), "image/png")},
                    data={"expected_part_no": sp.part_no, "run_quality": "true"})
    assert r.status_code == 200
    j = r.json()
    assert j["result"] in ("OK", "REVIEW")  # 正しい部品は誤出荷(NG=取り違え扱い)にならない
    assert j["processing_time_ms"] < 1000
    assert j["log_id"] is not None


def test_inspect_mismatch_is_not_passed(client):
    specs = generate_part_specs(12, 4, seed=7)
    sp = specs[0]
    wrong = next(s for s in specs if s.part_no != sp.part_no).part_no
    r = client.post("/api/v1/inspect",
                    files={"file": ("c.png", _png(sp, 8881), "image/png")},
                    data={"expected_part_no": wrong, "run_quality": "false"})
    j = r.json()
    # 取り違えは決して OK で通さない（NG か REVIEW）
    assert j["result"] != "OK"


def test_history_and_stats(client):
    assert "logs" in client.get("/api/v1/history?limit=10").json()
    assert client.get("/api/v1/stats").json()["n_inspections"] >= 1


def test_parts_listing(client):
    parts = client.get("/api/v1/parts").json()["parts"]
    assert len(parts) == 12
