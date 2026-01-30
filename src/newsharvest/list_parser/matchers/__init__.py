# -*- coding: utf-8 -*-
"""URL 匹配器模块"""

from .similarity import (
    URLSimilarityMatcher,
    URLSimilarityCalculator,
    URLParser,
    URLComponents,
    SegmentType,
    is_high_confidence_detail_url,
    filter_anchor_urls,
    filter_by_structure_clustering,
    find_similar_urls,
)
from .pattern import (
    URLPatternLearner,
    URLPatternMatcher,
    URLPattern,
    enhance_news_extraction,
)

__all__ = [
    "URLSimilarityMatcher",
    "URLSimilarityCalculator",
    "URLParser",
    "URLComponents",
    "SegmentType",
    "is_high_confidence_detail_url",
    "filter_anchor_urls",
    "filter_by_structure_clustering",
    "find_similar_urls",
    "URLPatternLearner",
    "URLPatternMatcher",
    "URLPattern",
    "enhance_news_extraction",
]

