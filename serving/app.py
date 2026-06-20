"""FastAPI serving app: top-K recommendations for a customer (Phase 7).

Concept — two-stage serving. Retrieval and feature aggregation are precomputed in
BigQuery, so the online path is fetch-then-rank: given a ``customer_id``, fetch the
customer's candidates with their features, run the saved ranker (or the cold-start
popularity fallback when the customer has no learned features), optionally apply the
guardrail re-ranker, and return the top-K as JSON with the response latency logged.

This is an honest architecture demonstration, not a production-throughput service.
The latency it reports includes a live BigQuery feature fetch per request; a real
deployment would serve those precomputed features from a low-latency store (the
"feature store in miniature" idea), and would precompute the co-purchase score that
this query derives on the fly. The README says so plainly.

``fastapi`` is imported lazily inside :func:`create_app`, so importing this module
(for the pure helpers below, or for type-checking) does not require FastAPI.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel

from core.config import Settings, get_settings
from core.logging import configure_logging
from guardrails.reranker import rerank
from models.fallback import fetch_candidate_features, popularity_recommend
from models.ranker import CatBoostRecommender, load_ranker

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Guardrail re-ranker settings used when ?diversify=true (mirrors the Phase 6 defaults).
RERANK_POOL = 100
RERANK_MAX_PER_CATEGORY = 3
RERANK_POPULARITY_CAP = 0.5


class RecommendationItem(BaseModel):
    """One recommended article, with the attributes a UI would show."""

    rank: int
    article_id: str
    prod_name: str
    product_type_name: str
    product_group_name: str
    colour_group_name: str
    price_tier: int
    popularity_recent: int


class RecommendationResponse(BaseModel):
    """The typed response: the list plus how it was produced and how long it took."""

    customer_id: str
    k: int
    served_by: str  # "ranker", "popularity_fallback", optionally "+reranked"
    cold_start: bool
    n_candidates: int
    latency_ms: float
    items: list[RecommendationItem]


def rerank_item_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-article attributes for the re-ranker: category + a bestseller flag.

    Bestsellers are the candidates retrieval tagged as global top sellers
    (``is_top_global``), so no popularity threshold needs to be recomputed online.
    """
    items = frame.drop_duplicates("article_id").set_index("article_id")
    return pd.DataFrame(
        {
            "product_group_name": items["product_group_name"].astype(str),
            "is_bestseller": items["is_top_global"] == 1,
        }
    )


def to_items(ranked: pd.DataFrame, frame: pd.DataFrame) -> list[RecommendationItem]:
    """Join a ranked ``(customer_id, article_id, rank)`` frame to display attributes."""
    attrs = frame.drop_duplicates("article_id").set_index("article_id")
    items: list[RecommendationItem] = []
    for row in ranked.sort_values("rank").itertuples(index=False):
        attr = attrs.loc[row.article_id]
        items.append(
            RecommendationItem(
                rank=int(row.rank),
                article_id=str(row.article_id),
                prod_name=str(attr["prod_name"]),
                product_type_name=str(attr["product_type_name"]),
                product_group_name=str(attr["product_group_name"]),
                colour_group_name=str(attr["colour_group_name"]),
                price_tier=int(attr["price_tier"]),
                popularity_recent=int(attr["popularity_recent"]),
            )
        )
    return items


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app, loading the saved ranker once at startup."""
    from fastapi import FastAPI, HTTPException, Query

    settings = settings or get_settings()
    configure_logging(settings.log_level)
    model, features = load_ranker(settings.artifacts_dir)
    ranker = CatBoostRecommender(model, features)

    app = FastAPI(title="H&M two-stage recommender", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/recommendations/{customer_id}", response_model=RecommendationResponse)
    def recommend(
        customer_id: str,
        k: int = Query(default=settings.top_k, ge=1, le=100),
        model: str = Query(default="smart", pattern="^(smart|popular)$"),
        diversify: bool = Query(default=False),
    ) -> RecommendationResponse:
        """Return top-K recommendations for one customer with a logged latency.

        ``model=smart`` (default) uses the learned ranker for warm customers;
        ``model=popular`` ranks the same candidates by recent popularity, so the
        demo can show the relevance-vs-variety contrast. Cold customers always fall
        back to popularity, since the ranker has no features for them.
        """
        start = time.perf_counter()
        frame = fetch_candidate_features(settings, [customer_id])
        if frame.empty:
            raise HTTPException(status_code=404, detail=f"no candidates for customer {customer_id}")

        cold_start = not bool(frame["is_warm"].iloc[0])
        pool_k = max(k, RERANK_POOL) if diversify else k
        if cold_start or model == "popular":
            ranked = popularity_recommend(frame, pool_k)
            served_by = "popularity_fallback" if cold_start else "popularity"
        else:
            ranked = ranker.recommend(frame, pool_k)
            served_by = "ranker"

        if diversify:
            ranked = rerank(
                ranked,
                rerank_item_features(frame),
                k=k,
                max_per_category=RERANK_MAX_PER_CATEGORY,
                popularity_cap=RERANK_POPULARITY_CAP,
            )
            served_by += "+reranked"
        else:
            ranked = ranked[ranked["rank"] <= k]

        items = to_items(ranked, frame)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "served %s for customer=%s k=%s in %.1f ms (%s candidates, cold_start=%s)",
            served_by,
            customer_id,
            k,
            latency_ms,
            len(frame),
            cold_start,
        )
        return RecommendationResponse(
            customer_id=customer_id,
            k=k,
            served_by=served_by,
            cold_start=cold_start,
            n_candidates=len(frame),
            latency_ms=latency_ms,
            items=items,
        )

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/demo", StaticFiles(directory=str(static_dir), html=True), name="demo")

    return app
