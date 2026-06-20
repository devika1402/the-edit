"""Two-tower retrieval model (optional stretch, Phase 8 / OD-1).

A learned retrieval model with separate customer and item embedding towers,
trained with TensorFlow Recommenders on sampled data. This is roadmap unless
time allows; if it is skipped, the README describes it as future work, not as
built. It may need a separate environment or Colab GPU, so nothing here is
imported by the core pipeline.

Not yet implemented — typed stub for the optional stretch phase.
"""

from __future__ import annotations

from pathlib import Path

from core.config import Settings


def train_two_tower(settings: Settings) -> Path:
    """Train the two-tower retrieval model and return the artifact path.

    Raises:
        NotImplementedError: always; this is an optional stretch goal (OD-1).
    """
    raise NotImplementedError("models.two_tower.train_two_tower is an optional stretch goal")
