# -*- coding: utf-8 -*-
"""
NewsHarvest - 智能新闻采集与解析库

一站式解决新闻列表页和详情页的采集与解析问题。

核心功能:
1. 新闻列表页解析 - 自动识别并提取新闻列表
2. 新闻详情页解析 - 基于 trafilatura 提取正文内容
3. 完整采集流程 - 从列表页到详情页的自动化采集

使用示例:

    from newsharvest import NewsHarvester

    # 创建采集器
    harvester = NewsHarvester()
    
    # 功能1: 采集并解析列表页
    result = harvester.fetch_list("https://news.example.com")
    for item in result.items:
        print(f"{item.title} - {item.url}")
    
    # 功能2: 解析列表页 HTML
    items = harvester.parse_list(html_content, base_url="...")
    
    # 功能3: 采集并解析详情页
    article = harvester.fetch_article("https://news.example.com/article/123")
    
    # 功能4: 解析详情页 HTML
    article = harvester.parse_article(html_content)
    
    # 功能5: 完整采集流程
    result = harvester.harvest("https://news.example.com")
    for article in result.articles:
        print(f"{article.title}: {len(article.content)} chars")
    
    # 关闭采集器
    harvester.close()
"""

from .models import (
    NewsItem,
    ArticleContent,
    NewsListResult,
    HarvestResult,
)
from .harvester import (
    NewsHarvester,
    HarvesterConfig,
    fetch_news_list,
    fetch_article_content,
    harvest_news,
)
from .list_parser import (
    NewsListExtractor,
    ListExtractorConfig,
    extract_news_list,
)
from .detail_parser import (
    parse_article,
    extract_article_content,
)
from .crawler import (
    WebCrawler,
    CrawlerConfig,
    fetch_html,
)
from .list_parser.utils.url import get_base_url

__version__ = "0.1.0"
__author__ = "Your Name"

__all__ = [
    # 主入口
    "NewsHarvester",
    "HarvesterConfig",
    
    # 数据模型
    "NewsItem",
    "ArticleContent",
    "NewsListResult",
    "HarvestResult",
    
    # 列表页解析
    "NewsListExtractor",
    "ListExtractorConfig",
    "extract_news_list",
    
    # 详情页解析
    "parse_article",
    "extract_article_content",
    
    # 爬虫
    "WebCrawler",
    "CrawlerConfig",
    "fetch_html",
    
    # 便捷函数
    "fetch_news_list",
    "fetch_article_content",
    "harvest_news",
    "get_base_url",
]

