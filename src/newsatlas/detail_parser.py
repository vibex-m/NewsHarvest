# -*- coding: utf-8 -*-
"""
新闻详情页解析模块

使用 trafilatura 进行详情页内容提取
"""

from typing import Optional, Union

from trafilatura import bare_extraction

from .models import ArticleContent
from .list_parser.utils.encoding import decode_html


def parse_article(
    html: Union[str, bytes],
    url: str = "",
    content_type: Optional[str] = None,
    include_comments: bool = False,
    include_tables: bool = True,
    include_links: bool = False,
    include_images: bool = False,
) -> ArticleContent:
    """
    解析新闻详情页内容
    
    Args:
        html: HTML 内容（str 或 bytes）
        url: 页面 URL（用于辅助解析）
        content_type: HTTP Content-Type 头（可选）
        include_comments: 是否包含评论
        include_tables: 是否包含表格
        include_links: 是否包含链接
        include_images: 是否包含图片
        
    Returns:
        ArticleContent 对象
    """
    # 处理编码
    if isinstance(html, bytes):
        html_str, _ = decode_html(html, content_type)
    else:
        html_str = html
    
    if not html_str:
        return ArticleContent(
            url=url,
            success=False,
            error="空 HTML 内容"
        )



    try:
        # 使用 trafilatura 提取
        extracted = bare_extraction(
            html_str,
            url=url,
            include_comments=include_comments,
            include_tables=include_tables,
            include_links=include_links,
            include_images=include_images,
            with_metadata=True,
        )
        
        if not extracted:
            return ArticleContent(
                url=url,
                success=False,
                error="trafilatura 提取失败"
            )
        
        # 处理返回结果（可能是 Document 对象或 dict）
        if hasattr(extracted, "as_dict"):
            data = extracted.as_dict()
        elif isinstance(extracted, dict):
            data = extracted
        else:
            # 尝试获取属性
            data = {
                "title": getattr(extracted, "title", None),
                "date": getattr(extracted, "date", None),
                "text": getattr(extracted, "text", None),
                "author": getattr(extracted, "author", None),
                "source": getattr(extracted, "source", None),
                "description": getattr(extracted, "description", None),
                "categories": getattr(extracted, "categories", []),
                "tags": getattr(extracted, "tags", []),
                "language": getattr(extracted, "language", None),
            }
        
        return ArticleContent(
            url=url,
            title=data.get("title"),
            content=data.get("text"),
            author=data.get("author"),
            publish_time=data.get("date"),
            source=data.get("source"),
            description=data.get("description"),
            categories=data.get("categories") or [],
            tags=data.get("tags") or [],
            language=data.get("language"),
            success=True,
        )
        
    except Exception as e:
        return ArticleContent(
            url=url,
            success=False,
            error=str(e)
        )


def extract_article_content(
    html: Union[str, bytes],
    url: str = "",
    content_type: Optional[str] = None,
) -> dict:
    """
    便捷函数：提取文章内容
    
    Args:
        html: HTML 内容
        url: 页面 URL
        content_type: Content-Type 头
        
    Returns:
        包含 title, content, author, publish_time 等字段的字典
    """
    result = parse_article(html, url, content_type)
    return result.as_dict()

