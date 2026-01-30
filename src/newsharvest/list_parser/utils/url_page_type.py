# -*- coding: utf-8 -*-
"""
URL 页面类型分类器

基于 URL 结构语义判断页面类型（列表页 vs 详情页）
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


class PageType(Enum):
    """页面类型"""
    INDEX = "index"      # 列表页/聚合页
    ARTICLE = "article"  # 详情页/文章页
    UNKNOWN = "unknown"  # 无法判断


@dataclass
class ClassifyResult:
    """分类结果"""
    page_type: PageType
    confidence: float
    reason: str


# 列表页特征词（路径中出现这些词倾向于列表页）
INDEX_KEYWORDS = {
    'index', 'list', 'category', 'tag', 'tags', 'archive', 'archives',
    'page', 'pages', 'topic', 'topics', 'channel', 'section', 'sections',
    'browse', 'search', 'results', 'all', 'latest', 'newest', 'popular',
    'hot', 'trending', 'top', 'featured', 'home', 'main', 'default',
}

# 详情页特征词（路径中出现这些词倾向于详情页）
ARTICLE_KEYWORDS = {
    'article', 'articles', 'news', 'story', 'stories', 'post', 'posts',
    'detail', 'details', 'content', 'view', 'read', 'show', 'item',
    'entry', 'blog', 'p', 'a', 'n', 'id',
}


def classify_url(url: str) -> ClassifyResult:
    """
    根据 URL 结构分类页面类型
    
    Args:
        url: URL 字符串
        
    Returns:
        ClassifyResult 分类结果
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 去除扩展名
        if '.' in path:
            path_no_ext = path.rsplit('.', 1)[0]
        else:
            path_no_ext = path
        
        segments = [s for s in path_no_ext.split('/') if s]
        
        if not segments:
            return ClassifyResult(PageType.INDEX, 0.8, "根路径")
        
        # 检查最后一个段
        last_seg = segments[-1]
        
        # 1. 列表页特征：最后一段是列表关键词
        if last_seg in INDEX_KEYWORDS:
            return ClassifyResult(PageType.INDEX, 0.85, f"列表关键词: {last_seg}")
        
        # 2. 详情页特征：包含长数字 ID
        if re.match(r'^\d{5,}$', last_seg):
            return ClassifyResult(PageType.ARTICLE, 0.9, f"长数字ID: {last_seg}")
        
        # 3. 详情页特征：包含日期路径
        if len(segments) >= 3:
            # 检查是否有 YYYY/MM/DD 或 YYYY/MM 模式
            for i in range(len(segments) - 2):
                if (segments[i].isdigit() and len(segments[i]) == 4 and
                    segments[i+1].isdigit() and len(segments[i+1]) <= 2):
                    return ClassifyResult(PageType.ARTICLE, 0.85, "日期路径结构")
        
        # 4. 详情页特征：slug 格式（包含多个连字符的长字符串）
        if '-' in last_seg and len(last_seg) > 15:
            hyphen_count = last_seg.count('-')
            if hyphen_count >= 2:
                return ClassifyResult(PageType.ARTICLE, 0.8, f"Slug格式: {hyphen_count}个连字符")
        
        # 5. 详情页特征：混合ID格式（如 content_123456）
        if '_' in last_seg:
            parts = last_seg.split('_')
            if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) >= 5:
                return ClassifyResult(PageType.ARTICLE, 0.85, f"混合ID: {last_seg}")
        
        # 6. 路径深度分析
        if len(segments) >= 3:
            # 深度 >= 3 且最后一段不是常见关键词，更可能是详情页
            if last_seg not in INDEX_KEYWORDS and last_seg not in ARTICLE_KEYWORDS:
                return ClassifyResult(PageType.ARTICLE, 0.6, f"深路径: 深度{len(segments)}")
        
        # 7. 检查是否有详情页关键词在路径中
        for seg in segments[:-1]:
            if seg in ARTICLE_KEYWORDS:
                return ClassifyResult(PageType.ARTICLE, 0.7, f"详情关键词: {seg}")
        
        # 默认：无法判断
        return ClassifyResult(PageType.UNKNOWN, 0.5, "无明确特征")
        
    except Exception:
        return ClassifyResult(PageType.UNKNOWN, 0.3, "解析失败")


def is_article_url(url: str, min_confidence: float = 0.6) -> bool:
    """
    判断 URL 是否为文章/详情页
    
    Args:
        url: URL 字符串
        min_confidence: 最小置信度阈值
        
    Returns:
        是否为文章页
    """
    result = classify_url(url)
    return result.page_type == PageType.ARTICLE and result.confidence >= min_confidence


def is_index_url(url: str, min_confidence: float = 0.6) -> bool:
    """
    判断 URL 是否为列表/索引页
    
    Args:
        url: URL 字符串
        min_confidence: 最小置信度阈值
        
    Returns:
        是否为列表页
    """
    result = classify_url(url)
    return result.page_type == PageType.INDEX and result.confidence >= min_confidence

