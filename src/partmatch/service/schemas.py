"""API リクエスト/レスポンスのスキーマ。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PartUpsert(BaseModel):
    part_no: str
    part_name: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    group_id: Optional[int] = None
    status: str = "active"
    accept_threshold: Optional[float] = None
    margin_threshold: Optional[float] = None


class FeedbackIn(BaseModel):
    inspection_log_id: Optional[int] = None
    correct_part_no: Optional[str] = None
    feedback_type: str = Field("confirm", description="confirm | correct | unknown")
    comment: Optional[str] = None
    created_by: Optional[str] = None


class BuildIndexIn(BaseModel):
    train: bool = True
    epochs: int = 60


class GenerateDemoIn(BaseModel):
    n_parts: int = 40
    n_groups: int = 10
    imgs_per_part: int = 6
    epochs: int = 60
    seed: int = 42


class ThresholdsIn(BaseModel):
    accept_threshold: Optional[float] = None
    review_threshold: Optional[float] = None
    margin_threshold: Optional[float] = None
    similar_margin_threshold: Optional[float] = None
    top_k: Optional[int] = None


class CalibrateIn(BaseModel):
    save: bool = True


class SelfTestIn(BaseModel):
    n_parts: int = 20
    seed: int = 0


class CandidateOut(BaseModel):
    part_no: str
    score: float
    confidence: float
    group_id: Optional[int] = None


class InspectResponse(BaseModel):
    result: str
    action: str
    predicted_part_no: Optional[str]
    expected_part_no: Optional[str]
    confidence: float
    margin: float
    top_candidates: List[CandidateOut]
    quality: dict
    reason: str
    processing_time_ms: float
    log_id: Optional[int] = None
