# -*- coding: utf-8 -*-
"""
URL 工具函数

提供 URL 验证、解析、过滤等功能
"""

import re
from urllib.parse import urlparse, urljoin
from typing import Optional, List


# 已知的外部服务域名（社交媒体、邮件、下载等）
EXTERNAL_SERVICE_DOMAINS = {
    # 社交媒体
    'facebook.com', 'www.facebook.com', 'm.facebook.com',
    'twitter.com', 'www.twitter.com', 'x.com',
    'instagram.com', 'www.instagram.com',
    'linkedin.com', 'www.linkedin.com',
    'youtube.com', 'www.youtube.com', 'm.youtube.com',
    'tiktok.com', 'www.tiktok.com',
    'weibo.com', 'www.weibo.com',
    'telegram.org', 't.me', 'web.telegram.org',
    'whatsapp.com', 'wa.me',
    'pinterest.com', 'www.pinterest.com',
    'reddit.com', 'www.reddit.com',
    'threads.net', 'www.threads.net',
    # 应用商店
    'play.google.com', 'apps.apple.com', 'itunes.apple.com',
    'microsoft.com', 'www.microsoft.com',
    # 邮件服务
    'mail.google.com', 'outlook.com', 'mail.yahoo.com',
    # 搜索引擎
    'google.com', 'www.google.com',
    'bing.com', 'www.bing.com',
    'baidu.com', 'www.baidu.com',
}

# 非新闻链接的URL模式（只保留最基础的，避免误伤）
NON_NEWS_URL_PATTERNS = [
    re.compile(r'^mailto:', re.I),
    re.compile(r'^tel:', re.I),
    re.compile(r'^javascript:', re.I),
    re.compile(r'^#'),
    re.compile(r'^data:', re.I),
    re.compile(r'/cdn-cgi/', re.I),  # Cloudflare CDN
    re.compile(r'/wp-content/uploads/', re.I),  # WordPress uploads
    re.compile(r'/wp-admin/', re.I),  # WordPress admin
    re.compile(r'\.(jpg|jpeg|png|gif|svg|webp|ico|pdf|zip|rar|exe|mp3|mp4|avi)$', re.I),
]

# 分页/列表导航URL模式（这些URL结构与列表页相似，不是详情页）
PAGINATION_URL_PATTERNS = [
    # 带锚点的分页：/news/breaknews/1/6#breaknews, /list/page/2#content
    re.compile(r'/\d+#\w+$'),
    # 纯分页参数：?page=2, ?p=3, ?pageNum=5
    re.compile(r'[?&](page|p|pageNum|pagenum|pn)=\d+$', re.I),
    # 路径分页：/page/2, /p/3（但要排除可能是文章ID的情况）
    re.compile(r'/page/\d+/?$', re.I),
    # 下划线分页：{id}_{page}.shtml, 159140_2.shtml, article_3.html
    # 匹配：xxx_2.shtml, xxx_3.html 等（页码通常是2-99的小数字）
    re.compile(r'/[^/]+_([2-9]|[1-9]\d)\.(s?html?|htm|asp|php|jsp)$', re.I),
]

# 无效标题模式（模板语法、占位符等）
INVALID_TITLE_PATTERNS = [
    re.compile(r'\{\{.*\}\}'),           # Vue/Angular 模板: {{item.title}}
    re.compile(r'\$\{.*\}'),             # ES6 模板字符串: ${title}
    re.compile(r'<%.*%>'),               # JSP/ASP 模板: <%=title%>
    re.compile(r'\{%.*%\}'),             # Jinja2/Django 模板: {%block%}
    re.compile(r'^\s*$'),                # 纯空白
    re.compile(r'^(null|undefined|N/A|loading\.{0,3})$', re.I),  # 占位符
]


def is_pagination_url(url: str) -> bool:
    """
    检查URL是否为分页/导航链接

    Args:
        url: 待检查的URL

    Returns:
        是否为分页链接
    """
    for pattern in PAGINATION_URL_PATTERNS:
        if pattern.search(url):
            return True
    return False


def is_valid_title(title: str, min_length: int = 5) -> bool:
    """
    检查标题是否有效

    过滤条件：
    1. 不能是模板语法 ({{...}}, ${...}, 等)
    2. 不能太短
    3. 不能是纯占位符

    Args:
        title: 待检查的标题
        min_length: 最小长度要求

    Returns:
        标题是否有效
    """
    if not title:
        return False

    title = title.strip()

    # 长度检查
    if len(title) < min_length:
        return False

    # 模板/占位符检查
    for pattern in INVALID_TITLE_PATTERNS:
        if pattern.search(title):
            return False

    return True


def get_base_url(url: str) -> str:
    """
    Get the base URL (scheme + netloc) from a given URL.

    Args:
        url: The full URL (e.g., "https://www.example.com/path/to/page")

    Returns:
        The base URL (e.g., "https://www.example.com")
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""


def get_root_domain(domain: str) -> str:
    """
    提取根域名（去除子域名前缀）

    Args:
        domain: 完整域名 (e.g., "news.example.com", "www.example.co.uk")

    Returns:
        根域名 (e.g., "example.com", "example.co.uk")
    """
    if not domain:
        return ""

    parts = domain.lower().split('.')

    # 处理常见的二级域名后缀
    common_second_level = {'com', 'co', 'org', 'net', 'edu', 'gov', 'ac', 'or'}

    if len(parts) >= 3 and parts[-2] in common_second_level:
        # 如 example.co.uk -> example.co.uk
        return '.'.join(parts[-3:])
    elif len(parts) >= 2:
        # 如 example.com -> example.com
        return '.'.join(parts[-2:])
    else:
        return domain


def get_domain_name(domain: str) -> str:
    """
    提取域名主体部分（不含 TLD 和子域名前缀）
    
    例如:
    - "news.cyol.com" -> "cyol"
    - "www.cyol.net" -> "cyol"
    - "example.co.uk" -> "example"
    
    Args:
        domain: 完整域名
        
    Returns:
        域名主体部分
    """
    if not domain:
        return ""
    
    parts = domain.lower().split('.')
    
    # 常见的 TLD 和二级 TLD
    common_tlds = {
        'com', 'net', 'org', 'edu', 'gov', 'cn', 'uk', 'jp', 'kr', 
        'hk', 'tw', 'io', 'co', 'me', 'info', 'biz'
    }
    common_second_level = {'com', 'co', 'org', 'net', 'edu', 'gov', 'ac', 'or'}
    
    # 从右往左找到第一个非 TLD 部分
    i = len(parts) - 1
    while i >= 0:
        if parts[i] not in common_tlds and parts[i] not in common_second_level:
            return parts[i]
        i -= 1
    
    # 如果全是 TLD，返回最左边的部分
    return parts[0] if parts else ""


def is_same_site(url: str, base_url: str) -> bool:
    """
    检查URL是否与基础URL属于同一站点（同根域名或同组织）

    支持以下情况：
    1. 完全相同的域名
    2. 同根域名的子域名（如 news.example.com 和 www.example.com）
    3. 同组织不同 TLD（如 cyol.com 和 cyol.net）

    Args:
        url: 待检查的URL
        base_url: 基础URL

    Returns:
        是否为同一站点
    """
    try:
        url_domain = urlparse(url).netloc.lower()
        base_domain = urlparse(base_url).netloc.lower()

        if not url_domain or not base_domain:
            return False

        # 1. 完全相同
        if url_domain == base_domain:
            return True

        # 2. 同根域名（允许子域名）
        url_root = get_root_domain(url_domain)
        base_root = get_root_domain(base_domain)

        if url_root == base_root:
            return True
        
        # 3. 同组织不同 TLD（如 cyol.com 和 cyol.net）
        # 比较域名主体部分
        url_name = get_domain_name(url_domain)
        base_name = get_domain_name(base_domain)
        
        if url_name and base_name and url_name == base_name:
            return True

        return False

    except Exception:
        return False


def is_external_service(url: str) -> bool:
    """
    检查URL是否为已知的外部服务（社交媒体、应用商店等）

    Args:
        url: 待检查的URL

    Returns:
        是否为外部服务
    """
    try:
        domain = urlparse(url).netloc.lower()
        root = get_root_domain(domain)

        # 检查完整域名
        if domain in EXTERNAL_SERVICE_DOMAINS:
            return True

        # 检查根域名
        if root in EXTERNAL_SERVICE_DOMAINS:
            return True

        return False
    except Exception:
        return False


def is_valid_news_candidate(url: str, base_url: str) -> bool:
    """
    检查URL是否为有效的新闻链接候选

    综合检查：
    1. 非特殊协议/资源
    2. 非分页/导航链接
    3. 非外部服务
    4. 同站点校验

    Args:
        url: 待检查的URL
        base_url: 基础URL

    Returns:
        是否为有效候选
    """
    if not url:
        return False

    # 检查非新闻URL模式
    for pattern in NON_NEWS_URL_PATTERNS:
        if pattern.search(url):
            return False

    # 检查分页URL模式
    if is_pagination_url(url):
        return False

    # 转换为绝对URL
    if not url.startswith(('http://', 'https://')):
        if base_url:
            url = urljoin(base_url, url)
        else:
            return False

    # 检查是否为外部服务
    if is_external_service(url):
        return False

    # 检查同站点
    if not is_same_site(url, base_url):
        return False

    return True


def filter_same_site_urls(urls: List[str], base_url: str) -> List[str]:
    """
    过滤URL列表，只保留同站点的有效新闻候选链接

    Args:
        urls: URL列表
        base_url: 基础URL

    Returns:
        过滤后的URL列表
    """
    result = []
    for url in urls:
        if is_valid_news_candidate(url, base_url):
            # 转换为绝对URL
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
            result.append(url)
    return result

