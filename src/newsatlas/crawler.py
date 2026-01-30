# -*- coding: utf-8 -*-
"""
HTTP 请求模块

处理网页请求、编码检测等
"""

import random
import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

import requests

from .list_parser.utils.encoding import decode_html


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    timeout: int = 5
    retry_times: int = 0
    retry_delay: float = 1.0
    random_delay: Tuple[float, float] = (0.5, 1.5)
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    headers: Optional[Dict[str, str]] = None


class WebCrawler:
    """网页爬虫"""
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self._session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """设置 Session 默认 headers"""
        default_headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if self.config.headers:
            default_headers.update(self.config.headers)
        self._session.headers.update(default_headers)
    
    def fetch(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取页面 HTML 内容
        
        Args:
            url: 页面 URL
            
        Returns:
            (html_content, error_message)
            成功时 error_message 为 None，失败时 html_content 为 None
        """
        last_error = None
        
        for attempt in range(self.config.retry_times + 1):
            try:
                response = self._session.get(
                    url,
                    timeout=self.config.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # 智能解码 HTML
                content_type = response.headers.get("Content-Type", "")
                html, encoding = decode_html(response.content, content_type)
                
                return html, None
                
            except requests.exceptions.Timeout:
                last_error = f"请求超时 (尝试 {attempt + 1}/{self.config.retry_times + 1})"
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP 错误: {e.response.status_code}"
                # HTTP 错误不重试
                break
            except requests.exceptions.RequestException as e:
                last_error = f"请求失败: {str(e)}"
            
            # 重试前等待
            if attempt < self.config.retry_times:
                time.sleep(self.config.retry_delay)
        
        return None, last_error
    
    def fetch_bytes(self, url: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """
        获取页面原始字节内容
        
        Args:
            url: 页面 URL
            
        Returns:
            (content_bytes, content_type, error_message)
        """
        try:
            response = self._session.get(
                url,
                timeout=self.config.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            return response.content, content_type, None
            
        except requests.exceptions.RequestException as e:
            return None, None, str(e)
    
    def delay(self):
        """随机延迟"""
        min_delay, max_delay = self.config.random_delay
        time.sleep(random.uniform(min_delay, max_delay))
    
    def close(self):
        """关闭 Session"""
        self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 便捷函数
def fetch_html(url: str, timeout: int = 15) -> Tuple[Optional[str], Optional[str]]:
    """
    获取页面 HTML 内容（便捷函数）
    
    Args:
        url: 页面 URL
        timeout: 超时时间
        
    Returns:
        (html_content, error_message)
    """
    config = CrawlerConfig(timeout=timeout)
    crawler = WebCrawler(config)
    try:
        return crawler.fetch(url)
    finally:
        crawler.close()

