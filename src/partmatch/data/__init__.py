"""合成データ生成（実部品画像が無い環境での検証用）。"""
from .synth import PartSpec, generate_part_specs, render_part, generate_dataset

__all__ = ["PartSpec", "generate_part_specs", "render_part", "generate_dataset"]
