"""照合判定エンジン（システムの中核・安全側設計）。

最大の危険は「間違っているのに OK を出す」誤出荷。これを防ぐため、AI は必ず
1つの答えを強制せず、以下の状態に分類する:

    OK      : 期待品番と一致し、十分な信頼度・マージンがある        -> pass
    NG      : 別品番である可能性が高い（取り違えの疑い）            -> block（出荷停止）
    REVIEW  : 曖昧（信頼度不足 / Top1-Top2 が僅差 / 類似グループ内） -> manual_check
    RETAKE  : 画質不良で判定不可                                    -> retake
    UNKNOWN : 該当なし（未登録品番の可能性）                        -> manual_check

判定は単純な Top-1 ではなく、(1) 受理しきい値、(2) Top1-Top2 マージン、
(3) 類似品番グループ内での追加マージン、(4) 品番別しきい値、を組み合わせる。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image

from ..quality.checks import assess_quality


def cos_to_conf(cos: float) -> float:
    """コサイン類似度 [-1,1] を信頼度 [0,1] へ写像（表示用）。"""
    return max(0.0, min(1.0, (cos + 1.0) / 2.0))


@dataclass
class Candidate:
    part_no: str
    score: float          # コサイン類似度
    confidence: float     # [0,1]
    group_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "part_no": self.part_no,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "group_id": self.group_id,
        }


@dataclass
class MatchResult:
    result: str
    action: str
    predicted_part_no: Optional[str]
    expected_part_no: Optional[str]
    confidence: float
    margin: float
    candidates: List[Candidate] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    reason: str = ""
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "action": self.action,
            "predicted_part_no": self.predicted_part_no,
            "expected_part_no": self.expected_part_no,
            "confidence": round(self.confidence, 4),
            "margin": round(self.margin, 4),
            "top_candidates": [c.to_dict() for c in self.candidates],
            "quality": self.quality,
            "reason": self.reason,
            "processing_time_ms": round(self.processing_time_ms, 2),
        }


class MatchEngine:
    def __init__(self, embedder, store, settings,
                 part_thresholds: Optional[Dict[str, dict]] = None,
                 rows_per_search: int = 50):
        self.embedder = embedder
        self.store = store
        self.s = settings
        self.part_thresholds = part_thresholds or {}
        self.rows_per_search = rows_per_search
        # 現場キャリブレーション済みの画質しきい値があれば読み込む
        self.quality_overrides: Dict[str, float] = {}
        qpath = Path(str(getattr(settings, "quality_thresholds_path", "")))
        if qpath and qpath.exists():
            try:
                self.quality_overrides = json.loads(qpath.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.quality_overrides = {}

    # --- ベクトル行 → 品番単位の候補に集約 ---
    def _aggregate(self, image: Image.Image, top_k: int) -> List[Candidate]:
        emb = self.embedder.embed_one(image)
        hits = self.store.search(emb, k=self.rows_per_search)
        best: Dict[str, Candidate] = {}
        for h in hits:
            pn = h.meta.get("part_no")
            if pn is None:
                continue
            if pn not in best or h.score > best[pn].score:
                best[pn] = Candidate(pn, h.score, cos_to_conf(h.score),
                                     h.meta.get("group_id"))
        cands = sorted(best.values(), key=lambda c: c.score, reverse=True)
        return cands[:top_k]

    def _thresholds_for(self, part_no: Optional[str]):
        accept = self.s.accept_threshold
        margin = self.s.margin_threshold
        if part_no and part_no in self.part_thresholds:
            o = self.part_thresholds[part_no]
            accept = o.get("accept_threshold", accept)
            margin = o.get("margin_threshold", margin)
        return accept, margin

    def inspect(self, image: Image.Image, expected_part_no: Optional[str] = None,
                run_quality: bool = True) -> MatchResult:
        t0 = time.perf_counter()

        # 1) 画質ゲート
        quality = {}
        if run_quality:
            qr = assess_quality(image, **self.quality_overrides)
            quality = qr.to_dict()
            if not qr.ok:
                return MatchResult(
                    result="RETAKE", action="retake",
                    predicted_part_no=None, expected_part_no=expected_part_no,
                    confidence=0.0, margin=0.0, candidates=[], quality=quality,
                    reason="画質不良のため再撮影が必要: " + ", ".join(qr.issues),
                    processing_time_ms=(time.perf_counter() - t0) * 1000,
                )

        # 2) 候補集約
        cands = self._aggregate(image, self.s.top_k)
        if not cands:
            return MatchResult(
                result="UNKNOWN", action="manual_check",
                predicted_part_no=None, expected_part_no=expected_part_no,
                confidence=0.0, margin=0.0, candidates=[], quality=quality,
                reason="登録ベクトルが存在しないか候補なし",
                processing_time_ms=(time.perf_counter() - t0) * 1000,
            )

        top1 = cands[0]
        top2 = cands[1] if len(cands) > 1 else None
        margin = top1.score - (top2.score if top2 else -1.0)

        accept, base_margin = self._thresholds_for(top1.part_no)
        review_thr = self.s.review_threshold
        # 類似グループ内が僅差なら追加マージンを要求
        req_margin = base_margin
        if top2 and top2.group_id is not None and top2.group_id == top1.group_id:
            req_margin = max(base_margin, self.s.similar_margin_threshold)

        strong = top1.score >= accept and margin >= req_margin

        # 3) 判定
        if expected_part_no:
            if top1.part_no == expected_part_no:
                if strong:
                    res, act = "OK", "pass"
                    reason = "期待品番と一致し、信頼度・マージンとも十分。"
                elif top1.score >= review_thr:
                    res, act = "REVIEW", "manual_check"
                    reason = ("期待品番が最有力だが、信頼度またはTop1-Top2マージンが"
                              f"不足（margin={margin:.3f} < 要求{req_margin:.3f}）。要確認。")
                else:
                    res, act = "REVIEW", "manual_check"
                    reason = "期待品番が最有力だが信頼度が低い。要確認。"
            else:
                # 期待と違う品番が最有力 = 取り違えの疑い
                exp = next((c for c in cands if c.part_no == expected_part_no), None)
                if strong:
                    res, act = "NG", "block"
                    reason = (f"期待品番 {expected_part_no} と異なる "
                              f"{top1.part_no} が高信頼で最有力。取り違えの疑い、出荷停止。")
                else:
                    res, act = "REVIEW", "manual_check"
                    reason = (f"最有力 {top1.part_no} が期待 {expected_part_no} と不一致だが"
                              "信頼度が低く確定不可。要確認。")
                if exp is not None:
                    reason += f"（期待品番のスコア={exp.score:.3f}）"
        else:
            # オープン識別（期待品番なし）
            if strong:
                res, act = "OK", "pass"
                reason = f"{top1.part_no} と高信頼で識別。"
            elif top1.score >= review_thr:
                res, act = "REVIEW", "manual_check"
                reason = "最有力候補はあるが確信度不足。Top候補を確認。"
            else:
                res, act = "UNKNOWN", "manual_check"
                reason = "登録品番に十分一致せず（未登録の可能性）。要確認。"

        return MatchResult(
            result=res, action=act,
            predicted_part_no=top1.part_no,
            expected_part_no=expected_part_no,
            confidence=top1.confidence, margin=float(margin),
            candidates=cands, quality=quality, reason=reason,
            processing_time_ms=(time.perf_counter() - t0) * 1000,
        )
