# -*- coding: utf-8 -*-
"""
NewsAtlas - 新闻采集主入口

提供5个核心功能：
1. 传入列表页URL，采集并返回解析出的结果
2. 传入新闻列表页HTML，解析新闻列表页的返回解析结果
3. 传入新闻详情页URL，采集并解析的新闻详情页
4. 传入新闻详情页HTML，解析返回新闻详情页解析结果
5. 传入列表页URL，解析出列表页，并且采集详情页，返回解析出的详情页
"""

import time
import random
from datetime import datetime
from typing import List, Optional, Union, Callable
from dataclasses import dataclass

from .models import NewsItem, ArticleContent, NewsListResult, HarvestResult
from .crawler import WebCrawler, CrawlerConfig, fetch_html
from .list_parser import NewsListExtractor, ListExtractorConfig, extract_news_list
from .detail_parser import parse_article, extract_article_content
from .list_parser.utils.url import get_base_url


@dataclass
class HarvesterConfig:
    """采集器配置"""
    # 爬虫配置
    timeout: int = 15
    retry_times: int = 2
    request_delay: tuple = (1.0, 2.0)  # 请求间隔范围
    
    # 列表页解析配置
    min_title_length: int = 8
    min_items_count: int = 3
    use_similarity_matching: bool = True
    similarity_threshold: float = 0.65  # URL相似度匹配阈值
    
    # 详情页采集配置
    max_articles_per_list: int = 50  # 每个列表页最多采集多少详情页
    
    # 回调配置
    on_article_fetched: Optional[Callable[[ArticleContent], None]] = None
    on_progress: Optional[Callable[[int, int], None]] = None


class NewsHarvester:
    """
    新闻采集器
    
    一站式解决新闻列表页和详情页的采集与解析
    
    使用示例:
    
        harvester = NewsHarvester()
        
        # 功能1: 采集并解析列表页
        result = harvester.fetch_list("https://news.example.com")
        for item in result.items:
            print(f"{item.title} - {item.url}")
        
        # 功能2: 解析列表页 HTML
        items = harvester.parse_list(html_content, base_url="https://news.example.com")
        
        # 功能3: 采集并解析详情页
        article = harvester.fetch_article("https://news.example.com/article/123")
        print(article.title, article.content)
        
        # 功能4: 解析详情页 HTML
        article = harvester.parse_article(html_content, url="https://...")
        
        # 功能5: 完整采集流程
        result = harvester.harvest("https://news.example.com")
        for article in result.articles:
            print(f"{article.title}: {len(article.content)} chars")
    """
    
    def __init__(self, config: Optional[HarvesterConfig] = None):
        """
        初始化采集器
        
        Args:
            config: 采集器配置
        """
        self.config = config or HarvesterConfig()
        
        # 初始化爬虫
        crawler_config = CrawlerConfig(
            timeout=self.config.timeout,
            retry_times=self.config.retry_times,
            random_delay=self.config.request_delay,
        )
        self.crawler = WebCrawler(crawler_config)
        
        # 初始化列表页解析器
        list_config = ListExtractorConfig(
            min_title_length=self.config.min_title_length,
            min_items_count=self.config.min_items_count,
            use_similarity_matching=self.config.use_similarity_matching,
            similarity_threshold=self.config.similarity_threshold,
        )
        self.list_extractor = NewsListExtractor(list_config)
    
    # ========== 功能1: 采集并解析列表页 ==========
    
    def fetch_list(self, url: str) -> NewsListResult:
        """
        功能1: 传入列表页URL，采集并返回解析出的结果
        
        Args:
            url: 列表页 URL
            
        Returns:
            NewsListResult 包含解析出的新闻列表
        """
        html, error = self.crawler.fetch(url)
        
        if error:
            return NewsListResult(
                url=url,
                success=False,
                error=error
            )
        
        base_url = get_base_url(url)
        items = self.list_extractor.extract(html, base_url)
        
        return NewsListResult(
            url=url,
            items=items,
            total_count=len(items),
            success=True
        )
    
    # ========== 功能2: 解析列表页 HTML ==========
    
    def parse_list(
        self,
        html: Union[str, bytes],
        base_url: str = "",
        content_type: Optional[str] = None
    ) -> List[NewsItem]:
        """
        功能2: 传入新闻列表页HTML，解析并返回新闻列表
        
        Args:
            html: HTML 内容（str 或 bytes）
            base_url: 基础 URL（用于转换相对链接）
            content_type: HTTP Content-Type 头（可选）
            
        Returns:
            NewsItem 列表
        """
        return self.list_extractor.extract(html, base_url, content_type=content_type)
    
    # ========== 功能3: 采集并解析详情页 ==========
    
    def fetch_article(self, url: str) -> ArticleContent:
        """
        功能3: 传入新闻详情页URL，采集并解析详情页内容
        
        Args:
            url: 详情页 URL
            
        Returns:
            ArticleContent 包含解析出的文章内容
        """
        html, error = self.crawler.fetch(url)
        
        if error:
            return ArticleContent(
                url=url,
                success=False,
                error=error,
                crawled_at=datetime.now().isoformat()
            )
        
        result = parse_article(html, url)
        result.crawled_at = datetime.now().isoformat()
        return result
    
    # ========== 功能4: 解析详情页 HTML ==========
    
    def parse_article(
        self,
        html: Union[str, bytes],
        url: str = "",
        content_type: Optional[str] = None
    ) -> ArticleContent:
        """
        功能4: 传入新闻详情页HTML，解析并返回文章内容
        
        Args:
            html: HTML 内容（str 或 bytes）
            url: 页面 URL（用于辅助解析）
            content_type: HTTP Content-Type 头（可选）
            
        Returns:
            ArticleContent 包含解析出的文章内容
        """
        return parse_article(html, url, content_type)
    
    # ========== 功能5: 完整采集流程 ==========
    
    def harvest(
        self,
        list_url: str,
        max_articles: Optional[int] = None
    ) -> HarvestResult:
        """
        功能5: 传入列表页URL，解析列表页并采集所有详情页
        
        完整采集流程：
        1. 采集并解析列表页
        2. 遍历所有新闻链接
        3. 采集并解析每个详情页
        4. 返回所有详情页内容
        
        Args:
            list_url: 列表页 URL
            max_articles: 最多采集多少篇文章（默认使用配置）
            
        Returns:
            HarvestResult 包含列表和所有文章内容
        """
        max_count = max_articles or self.config.max_articles_per_list
        
        # 步骤1: 采集并解析列表页
        list_result = self.fetch_list(list_url)
        
        if not list_result.success:
            return HarvestResult(
                list_url=list_url,
                list_items=[],
                articles=[],
            )
        
        # 步骤2: 采集详情页
        articles = []
        success_count = 0
        failed_count = 0
        
        items_to_fetch = list_result.items[:max_count]
        total = len(items_to_fetch)
        
        for i, item in enumerate(items_to_fetch):
            # 进度回调
            if self.config.on_progress:
                self.config.on_progress(i + 1, total)
            
            # 采集详情页
            article = self.fetch_article(item.url)
            
            # 补充列表页的信息
            if not article.title and item.title:
                article.title = item.title
            if not article.publish_time and item.publish_time:
                article.publish_time = item.publish_time
            
            if article.success and article.content:
                success_count += 1
            else:
                failed_count += 1
            
            articles.append(article)
            
            # 文章采集回调
            if self.config.on_article_fetched:
                self.config.on_article_fetched(article)
            
            # 请求间隔（最后一个不需要等待）
            if i < total - 1:
                self.crawler.delay()
        
        return HarvestResult(
            list_url=list_url,
            list_items=list_result.items,
            articles=articles,
            success_count=success_count,
            failed_count=failed_count,
        )
    
    def close(self):
        """关闭采集器，释放资源"""
        self.crawler.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ========== 便捷函数 ==========

def fetch_news_list(url: str, timeout: int = 15) -> List[dict]:
    """
    便捷函数：采集并解析新闻列表页
    
    Args:
        url: 列表页 URL
        timeout: 请求超时时间
        
    Returns:
        新闻列表（字典格式）
    """
    config = HarvesterConfig(timeout=timeout)
    with NewsHarvester(config) as harvester:
        result = harvester.fetch_list(url)
        return [item.as_dict() for item in result.items]


def fetch_article_content(url: str, timeout: int = 15) -> dict:
    """
    便捷函数：采集并解析新闻详情页
    
    Args:
        url: 详情页 URL
        timeout: 请求超时时间
        
    Returns:
        文章内容（字典格式）
    """
    config = HarvesterConfig(timeout=timeout)
    with NewsHarvester(config) as harvester:
        result = harvester.fetch_article(url)
        return result.as_dict()


def harvest_news(
    list_url: str,
    max_articles: int = 20,
    timeout: int = 15
) -> dict:
    """
    便捷函数：完整采集新闻列表和详情页
    
    Args:
        list_url: 列表页 URL
        max_articles: 最多采集多少篇文章
        timeout: 请求超时时间
        
    Returns:
        采集结果（字典格式）
    """
    config = HarvesterConfig(
        timeout=timeout,
        max_articles_per_list=max_articles
    )
    with NewsHarvester(config) as harvester:
        result = harvester.harvest(list_url, max_articles)
        return result.as_dict()

