# -*- coding: utf-8 -*-
"""
数据模型定义

定义新闻列表项和新闻内容的数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class NewsItem:
    """新闻列表项"""
    title: str
    url: str
    publish_time: Optional[str] = None
    timestamp: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "publish_time": self.publish_time,
            "timestamp": self.timestamp
        }


@dataclass
class ArticleContent:
    """新闻详情页内容"""
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    publish_time: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    language: Optional[str] = None
    
    # 原始数据
    raw_html: Optional[str] = None
    
    # 元数据
    crawled_at: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "publish_time": self.publish_time,
            "source": self.source,
            "description": self.description,
            "categories": self.categories,
            "tags": self.tags,
            "language": self.language,
            "crawled_at": self.crawled_at,
            "success": self.success,
            "error": self.error,
        }
    
    @property
    def is_valid(self) -> bool:
        """检查内容是否有效"""
        return self.success and self.content is not None and len(self.content) > 50


@dataclass
class NewsListResult:
    """新闻列表解析结果"""
    url: str
    items: List[NewsItem] = field(default_factory=list)
    total_count: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "items": [item.as_dict() for item in self.items],
            "total_count": self.total_count,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class AtlasResult:
    """采集结果（列表页 + 详情页）"""
    list_url: str
    list_items: List[NewsItem] = field(default_factory=list)
    articles: List[ArticleContent] = field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "list_url": self.list_url,
            "list_items": [item.as_dict() for item in self.list_items],
            "articles": [article.as_dict() for article in self.articles],
            "success_count": self.success_count,
            "failed_count": self.failed_count,
        }

