# -*- coding: utf-8 -*-
"""
新闻列表页提取器
基于 Readability 和 Trafilatura 的设计思想实现

设计思想：
1. 评分机制 - 给列表容器和列表项打分
2. XPath + CSS选择器 - 预定义常见新闻列表的选择模式
3. 启发式规则 - 基于class/id特征识别新闻列表
4. 时间解析 - 多种时间格式的识别和解析
5. 链接密度分析 - 区分导航区域和正文列表
6. 结构学习 - 从种子链接学习DOM结构，匹配更多相似内容
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set, Dict, Union
from urllib.parse import urljoin, urlparse

from lxml.html import HtmlElement, fromstring

from ..models import NewsItem
from .utils.context import LinkContextExtractor
from .utils.encoding import decode_html
from .matchers.similarity import (
    URLSimilarityMatcher,
    is_high_confidence_detail_url, filter_anchor_urls,
    filter_by_structure_clustering, NON_DETAIL_PREFIXES
)
from .utils.url import is_valid_news_candidate, is_valid_title


def ensure_html_string(html: Union[str, bytes], content_type: Optional[str] = None) -> str:
    """
    确保HTML内容为正确解码的字符串
    """
    if not html:
        return ""
    
    if isinstance(html, str):
        if _has_encoding_issues(html):
            try:
                html_bytes = html.encode('latin-1')
                decoded, _ = decode_html(html_bytes, content_type)
                return decoded
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        return html
    elif isinstance(html, bytes):
        decoded, _ = decode_html(html, content_type)
        return decoded
    else:
        raise TypeError(f"html must be str or bytes, got {type(html)}")


def _has_encoding_issues(text: str) -> bool:
    """检测字符串是否有编码问题"""
    utf8_as_latin1_pattern = re.compile(r'[\xc0-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}')
    if utf8_as_latin1_pattern.search(text):
        return True
    if '\ufffd' in text:
        return True
    return False


@dataclass
class ListExtractorConfig:
    """提取器配置"""
    min_title_length: int = 8
    max_title_length: int = 200
    min_items_count: int = 3
    score_threshold: float = 0.5
    min_link_text_ratio: float = 0.3
    use_similarity_matching: bool = True
    similarity_threshold: float = 0.65


class NewsListExtractor:
    """
    新闻列表页提取器
    """

    REGEXPS = {
        "list_positive": re.compile(
            r"news[_-]?list|article[_-]?list|story[_-]?list|post[_-]?list|"
            r"list[_-]?content|list[_-]?item|feed|entry|"
            r"hot[_-]?box|yaowen|xinwen|liebiao|zixun|dongtai",
            re.I
        ),
        "list_negative": re.compile(
            r"^nav$|^menu$|navigation|sidebar|footer|header|banner|"
            r"^ad$|advert|comment|share[_-]?box|"
            r"pagination|pager|widget|breadcrumb|login|search|"
            r"copyright|contact|about",
            re.I
        ),
        "nav_pattern": re.compile(
            r"nav|menu|tab|category|channel|section[_-]?link|"
            r"sub[_-]?nav|top[_-]?nav|main[_-]?nav",
            re.I
        ),
        "time_class": re.compile(
            r"time|date|pubdate|publish|posted|datetime|created|modified|"
            r"shijian|riqi|fabu",
            re.I
        ),
    }

    LIST_CONTAINER_XPATHS = [
        '//main//ul | //main//ol | //main//div[contains(@class, "list")]',
        '//article/parent::*',
        '//*[contains(@class, "news-list") or contains(@class, "newsList") or contains(@class, "news_list")]',
        '//*[contains(@class, "article-list") or contains(@class, "articleList") or contains(@class, "article_list")]',
        '//*[contains(@class, "list-content") or contains(@class, "listContent") or contains(@class, "list_content")]',
        '//*[contains(@class, "post-list") or contains(@class, "postList") or contains(@class, "post_list")]',
        '//*[contains(@id, "news-list") or contains(@id, "newsList") or contains(@id, "news_list")]',
        '//*[contains(@id, "article-list") or contains(@id, "articleList") or contains(@id, "article_list")]',
        '//*[contains(@id, "list-content") or contains(@id, "listContent") or contains(@id, "list_content")]',
        '//ul[count(li) >= 3]',
        '//div[count(div) >= 3 or count(article) >= 3]',
    ]

    NEWS_ITEM_XPATHS = [
        './li | ./div | ./article | ./section | ./a',
    ]

    TITLE_XPATHS = [
        './/h1/a | .//h2/a | .//h3/a | .//h4/a',
        './/a[.//h2 or .//h3]',
        './/a[contains(@class, "title") or contains(@class, "Title")]',
        './/a[contains(@class, "headline") or contains(@class, "Headline")]',
        './/*[contains(@class, "title") or contains(@class, "Title")]//a',
        './/*[contains(@class, "headline") or contains(@class, "Headline")]//a',
        './/h1 | .//h2 | .//h3 | .//h4',
        './/a[string-length(normalize-space(.)) > 15]',
    ]

    TIME_XPATHS = [
        './/time[@datetime]',
        './/*[contains(@class, "time") or contains(@class, "Time")]',
        './/*[contains(@class, "date") or contains(@class, "Date")]',
        './/*[contains(@class, "publish") or contains(@class, "Publish")]',
        './/span[contains(@class, "info")]',
    ]

    def __init__(self, config: Optional[ListExtractorConfig] = None):
        self.config = config or ListExtractorConfig()

    def extract(
        self,
        html: Union[str, bytes],
        base_url: str = "",
        use_structure_learning: bool = True,
        content_type: Optional[str] = None
    ) -> List[NewsItem]:
        """
        提取新闻列表
        """
        html_str = ensure_html_string(html, content_type)
        
        # 空HTML检查
        if not html_str or not html_str.strip():
            return []

        try:
            tree = fromstring(html_str)
        except Exception:
            return []

        self._clean_tree(tree)

        if use_structure_learning:
            heatmap_items = self._extract_by_dom_heatmap(tree, base_url)
            if heatmap_items and len(heatmap_items) >= 3:
                return self._final_validation(heatmap_items, base_url)

        candidates = self._find_list_containers_by_xpath(tree)
        candidates.extend(self._find_list_containers_by_heuristics(tree))

        seen = set()
        unique_candidates = []
        for c in candidates:
            elem_id = id(c)
            if elem_id not in seen:
                seen.add(elem_id)
                unique_candidates.append(c)

        all_results: List[Tuple[float, List[NewsItem]]] = []
        high_confidence_small_items: List[NewsItem] = []

        for container in unique_candidates:
            if self._is_navigation_container(container):
                continue

            items = self._extract_items_from_container(container, base_url)

            if len(items) >= self.config.min_items_count:
                score = self._score_items(items)
                all_results.append((score, items))
            elif 1 <= len(items) < self.config.min_items_count:
                for item in items:
                    if self._is_high_confidence_news_item(item):
                        high_confidence_small_items.append(item)

        if not all_results:
            items = self._extract_all_news_links(tree, base_url)
            if items:
                all_results.append((self._score_items(items), items))

        if not all_results:
            return []

        all_results.sort(key=lambda x: x[0], reverse=True)
        best_score = all_results[0][0]

        merged_items: List[NewsItem] = []
        seen_urls: Set[str] = set()

        for score, items in all_results:
            if score >= best_score * 0.6:
                for item in items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        merged_items.append(item)

        if merged_items and high_confidence_small_items:
            for item in high_confidence_small_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    merged_items.append(item)

        merged_items = self._final_validation(merged_items, base_url)

        return merged_items

    def _extract_by_dom_heatmap(
        self,
        tree: HtmlElement,
        base_url: str
    ) -> List[NewsItem]:
        """DOM 热点驱动的新闻提取"""
        try:
            from .utils.diffusion import DOMHeatmapClusterer, DiffusionBoundaryFinder
        except ImportError:
            return []

        all_links = []
        for link in tree.xpath("//a[@href]"):
            href = link.get("href", "")
            if not href or href.startswith(("javascript:", "#", "mailto:", "tel:", "data:")):
                continue

            if base_url and not href.startswith(("http://", "https://")):
                try:
                    full_url = urljoin(base_url, href)
                except:
                    continue
            else:
                full_url = href

            if is_valid_news_candidate(full_url, base_url):
                all_links.append((full_url, link))

        if len(all_links) < 3:
            return []

        all_urls = list(set([url for url, _ in all_links]))
        url_to_element = {}
        for url, elem in all_links:
            if url not in url_to_element:
                url_to_element[url] = elem
            else:
                existing_elem = url_to_element[url]
                existing_text = (existing_elem.text_content() or "").strip()
                new_text = (elem.text_content() or "").strip()

                if len(new_text) > len(existing_text) and len(new_text) >= 5:
                    url_to_element[url] = elem

        anchor_urls = filter_anchor_urls(all_urls)

        if len(anchor_urls) < 2:
            return []

        anchor_set = set(anchor_urls)
        candidate_urls = [url for url in all_urls if url not in anchor_set]

        matched_urls = set(anchor_urls)

        if candidate_urls and self.config.use_similarity_matching:
            try:
                threshold = self.config.similarity_threshold
                matcher = URLSimilarityMatcher(threshold=threshold)
                matched_results = matcher.find_similar(list(anchor_urls), candidate_urls)
                for url, score in matched_results:
                    matched_urls.add(url)
            except Exception:
                pass

        lit_elements = set()
        url_to_lit_element = {}

        for url in matched_urls:
            if url in url_to_element:
                elem = url_to_element[url]
                lit_elements.add(elem)
                url_to_lit_element[url] = elem

        if len(lit_elements) < 2:
            return []

        # 初始化上下文提取器（V3：可用扩散边界算法更稳地提取时间/标题）
        # 这里把 matched_urls 作为 anchor_urls 传入，以启用 utils/context.py 中的扩散边界时间提取。
        context_extractor: Optional[LinkContextExtractor] = None
        try:
            context_extractor = LinkContextExtractor(tree, base_url, anchor_urls=set(matched_urls))
        except Exception:
            context_extractor = None

        clusterer = DOMHeatmapClusterer(tree, lit_elements)
        clusterer.build_heatmap()
        zones = clusterer.find_hot_zones(min_zone_size=2)

        if not zones:
            zones = [(tree, lit_elements)]

        items = []
        seen_urls = set()

        for zone_root, zone_elements in zones:
            zone_items = self._extract_items_from_hot_zone(
                zone_root, zone_elements, url_to_lit_element, base_url, context_extractor
            )

            for item in zone_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)

        return items

    def _extract_items_from_hot_zone(
        self,
        zone_root: HtmlElement,
        zone_elements: Set[HtmlElement],
        url_to_element: Dict[str, HtmlElement],
        base_url: str,
        context_extractor: Optional[LinkContextExtractor] = None,
    ) -> List[NewsItem]:
        """从热区提取新闻 item"""
        try:
            from .utils.diffusion import DiffusionBoundaryFinder
        except ImportError:
            return []

        items = []
        element_to_url = {elem: url for url, elem in url_to_element.items()}
        boundary_finder = DiffusionBoundaryFinder(zone_elements)

        for elem in zone_elements:
            url = element_to_url.get(elem)
            if not url:
                continue

            boundary_root, boundary_elems, depth = boundary_finder.find_boundary(elem)

            if boundary_root is None:
                boundary_root = elem

            title = self._extract_title_from_boundary(elem, boundary_root)

            # 优先使用上下文提取器（若启用扩散边界算法，会更严格地限定时间来源）
            publish_time: Optional[str] = None
            timestamp: Optional[int] = None
            if context_extractor is not None:
                try:
                    ctx_title, ctx_time, ctx_ts = context_extractor.extract_context(url)
                    # 标题：如果上下文提取到更长且像标题的文本，则替换
                    if ctx_title and len(ctx_title) >= self.config.min_title_length:
                        if not title or len(ctx_title) > len(title):
                            title = self._clean_title(ctx_title)
                    # 时间：优先使用上下文提取结果
                    if ctx_time:
                        publish_time, timestamp = ctx_time, ctx_ts
                except Exception:
                    pass

            # 回退：如果上下文没拿到时间，用边界内规则提取
            if publish_time is None:
                publish_time, timestamp = self._extract_time_from_boundary(boundary_root)

            if title and len(title) >= self.config.min_title_length:
                items.append(NewsItem(
                    title=title,
                    url=url,
                    publish_time=publish_time,
                    timestamp=timestamp
                ))

        return items

    def _extract_title_from_boundary(
        self,
        link_elem: HtmlElement,
        boundary_root: HtmlElement
    ) -> str:
        """从边界容器提取标题"""
        link_text = (link_elem.text_content() or "").strip()

        if len(link_text) >= 15:
            return self._clean_title(link_text)

        for xpath in ['.//h1', './/h2', './/h3', './/h4',
                      './/*[contains(@class, "title")]',
                      './/*[contains(@class, "headline")]']:
            try:
                elems = boundary_root.xpath(xpath)
                for e in elems:
                    text = (e.text_content() or "").strip()
                    if len(text) >= 10:
                        return self._clean_title(text)
            except:
                pass

        return self._clean_title(link_text) if link_text else ""

    def _extract_time_from_boundary(
        self,
        boundary_root: HtmlElement
    ) -> Tuple[Optional[str], Optional[int]]:
        """从边界容器提取时间"""
        try:
            time_elem = boundary_root.xpath('.//time[@datetime]')
            if time_elem:
                datetime_str = time_elem[0].get('datetime', '')
                if datetime_str:
                    return datetime_str, None

            for xpath in [
                './/*[contains(@class, "time")]',
                './/*[contains(@class, "date")]',
                './/*[contains(@class, "publish")]',
            ]:
                elems = boundary_root.xpath(xpath)
                for e in elems:
                    text = (e.text_content() or "").strip()
                    if text and len(text) < 50:
                        return text, None
        except:
            pass

        return None, None

    def _clean_title(self, title: str) -> str:
        """清理标题文本"""
        if not title:
            return ""
        title = " ".join(title.split())
        title = re.sub(r'^[\[\]【】\(\)（）·•\-]+\s*', '', title)
        return title.strip()

    def _final_validation(
        self,
        items: List[NewsItem],
        base_url: str
    ) -> List[NewsItem]:
        """最终验证"""
        from .utils.url import is_valid_title, is_pagination_url

        valid_items = []
        seen_urls = set()

        for item in items:
            if item.url in seen_urls:
                continue

            if not is_valid_title(item.title, min_length=self.config.min_title_length):
                continue

            if is_pagination_url(item.url):
                continue

            seen_urls.add(item.url)
            valid_items.append(item)

        if len(valid_items) >= 5:
            valid_items = self._filter_by_url_structure(valid_items)

        return valid_items

    def _filter_by_url_structure(self, items: List[NewsItem]) -> List[NewsItem]:
        """使用URL结构聚类过滤"""
        urls = [item.url for item in items]
        main_urls = filter_by_structure_clustering(urls)
        main_url_set = set(main_urls)
        return [item for item in items if item.url in main_url_set]

    def _is_navigation_container(self, elem: HtmlElement) -> bool:
        """判断是否为导航容器"""
        class_id = self._get_class_id(elem)

        if elem.tag in ("nav", "header", "footer"):
            return True

        role = elem.get("role", "")
        if role in ("navigation", "menu", "menubar"):
            return True

        if self.REGEXPS["nav_pattern"].search(class_id):
            links = elem.xpath(".//a")
            if links:
                avg_len = sum(len((l.text_content() or "").strip()) for l in links) / len(links)
                if avg_len < 10:
                    return True

        return False

    def _extract_all_news_links(self, tree: HtmlElement, base_url: str) -> List[NewsItem]:
        """全局提取所有可能的新闻链接"""
        items = []
        seen_urls: Set[str] = set()

        main_areas = tree.xpath("//main | //article | //*[@role='main']")
        search_area = main_areas[0] if main_areas else tree

        priority_links = search_area.xpath(".//a[.//h2 or .//h3][@href]")
        title_class_links = search_area.xpath(
            './/a[.//*[contains(@class, "title") or contains(@class, "Title") or '
            'contains(@class, "headline") or contains(@class, "Headline")]][@href]'
        )
        item_class_links = search_area.xpath(
            './/a[contains(@class, "post-item") or contains(@class, "article-item") or '
            'contains(@class, "news-item") or contains(@class, "story-item") or '
            'contains(@class, "list-item")][@href]'
        )
        regular_links = search_area.xpath(".//a[@href]")

        all_links = []
        seen_link_ids = set()
        for link_list in [priority_links, title_class_links, item_class_links, regular_links]:
            for link in link_list:
                link_id = id(link)
                if link_id not in seen_link_ids:
                    seen_link_ids.add(link_id)
                    all_links.append(link)

        for link in all_links:
            parent = link.getparent()
            in_nav = False
            for _ in range(5):
                if parent is None:
                    break
                if parent.tag in ("body", "html"):
                    break
                if parent.tag in ("nav", "header", "footer"):
                    in_nav = True
                    break
                parent_class = self._get_class_id(parent)
                if self.REGEXPS["nav_pattern"].search(parent_class):
                    in_nav = True
                    break
                parent = parent.getparent()

            if in_nav:
                continue

            title = None

            for tag in ['h2', 'h3', 'h4', 'h1']:
                h_elem = link.find(f".//{tag}")
                if h_elem is not None:
                    title = self._get_text(h_elem)
                    break

            if not title or len(title) < self.config.min_title_length:
                for elem in link.iter():
                    elem_class = elem.get('class', '')
                    if elem_class and any(cls in elem_class.lower() for cls in ['title', 'headline']):
                        title = self._get_text(elem)
                        if title and len(title) >= self.config.min_title_length:
                            break

            if not title or len(title) < self.config.min_title_length:
                title = self._get_clean_link_text(link)

            url = link.get("href", "")
            if not title or len(title) < self.config.min_title_length:
                continue

            if base_url:
                try:
                    url = urljoin(base_url, url)
                except:
                    continue

            if not self._is_valid_news_url(url, base_url):
                continue

            if url not in seen_urls:
                seen_urls.add(url)
                context_extractor = LinkContextExtractor(tree, base_url)
                time_str = context_extractor._extract_time_from_node_context(link)
                items.append(NewsItem(title=title, url=url, publish_time=time_str))

        return items

    def _extract_items_from_container(self, container: HtmlElement, base_url: str) -> List[NewsItem]:
        """从列表容器中提取新闻项"""
        items = []
        for tag_xpath in self.NEWS_ITEM_XPATHS:
            for node in container.xpath(tag_xpath):
                title = None
                url = None

                title_link = None
                h_title_elem = node.find(".//h1")
                if h_title_elem is None:
                    h_title_elem = node.find(".//h2")
                if h_title_elem is None:
                    h_title_elem = node.find(".//h3")
                if h_title_elem is None:
                    h_title_elem = node.find(".//h4")

                if h_title_elem is not None:
                    a_in_h = h_title_elem.find(".//a")
                    if a_in_h is not None:
                        title_link = a_in_h
                        title = self._get_text(a_in_h)
                    else:
                        parent = h_title_elem.getparent()
                        if parent is not None and parent.tag == 'a':
                            title_link = parent
                            title = self._get_text(h_title_elem)
                        else:
                            title = self._get_text(h_title_elem)

                if title_link is None:
                    links = node.findall(".//a")
                    best_link = None
                    max_len = 0
                    for l in links:
                        l_text = self._get_clean_link_text(l)
                        if l_text and len(l_text) > max_len:
                            max_len = len(l_text)
                            best_link = l
                            title = l_text

                    if best_link is not None and max_len >= self.config.min_title_length:
                        title_link = best_link

                if title_link is None or not title or len(title) < self.config.min_title_length:
                    continue

                url = title_link.get("href", "")
                if base_url:
                    try:
                        url = urljoin(base_url, url)
                    except:
                        continue

                if not self._is_valid_news_url(url, base_url):
                    continue

                time_str = None
                timestamp = None

                temp_context = LinkContextExtractor(node, base_url)
                time_str = temp_context._extract_time_from_node_context(node)

                if time_str:
                    timestamp = temp_context._normalize_time(time_str)

                items.append(NewsItem(
                    title=title,
                    url=url,
                    publish_time=time_str,
                    timestamp=timestamp
                ))

        return items

    def _score_items(self, items: List[NewsItem]) -> float:
        """给新闻列表打分"""
        if not items:
            return 0.0

        score = 0
        count_score = min(len(items), 20) * 1.5
        score += count_score

        title_lengths = [len(item.title) for item in items]
        avg_len = sum(title_lengths) / len(title_lengths)
        if 15 <= avg_len <= 50:
            score += 20
        elif avg_len > 50:
            score += 10

        time_count = sum(1 for item in items if item.publish_time)
        time_ratio = time_count / len(items)
        score += time_ratio * 30

        paths = [urlparse(item.url).path for item in items]
        depths = [len(p.split('/')) for p in paths]
        if len(set(depths)) == 1:
            score += 20

        short_path_ratio = sum(
            1 for item in items
            if len([p for p in urlparse(item.url).path.split("/") if p]) <= 1
        ) / len(items)
        if short_path_ratio > 0.5:
            score -= 100

        short_titles = sum(1 for l in title_lengths if l < 10)
        if short_titles > len(items) * 0.3:
            score -= 30

        return max(score, 0)

    def _is_valid_news_url(self, url: str, base_url: str) -> bool:
        """检查URL是否是有效的新闻链接"""
        if not is_valid_news_candidate(url, base_url):
            return False

        parsed = urlparse(url)
        path = parsed.path.lower()
        if path.endswith((".jpg", ".png", ".gif", ".css", ".js", ".pdf", ".zip")):
            return False

        blacklist = ["/login", "/register", "/contact", "/lien-he", "/about", "/search", "/tag/"]
        path_lower = path.lower()
        if any(word in path_lower for word in blacklist):
            return False

        return True

    def _is_high_confidence_news_item(self, item: NewsItem) -> bool:
        """检查一个新闻项是否具有高置信度"""
        if len(item.title) < 15:
            return False

        parsed = urlparse(item.url)
        path_segments = [s for s in parsed.path.split('/') if s]
        if len(path_segments) < 2:
            return False

        path_lower = parsed.path.lower()
        news_patterns = [
            '/article', '/news', '/story', '/post', '/detail',
            '/chi-tiet', '/tin-chi-tiet',
            '/tin-', '/bai-viet',
            '/a/', '/p/', '/n/',
        ]

        has_news_pattern = any(pattern in path_lower for pattern in news_patterns)
        has_numeric_id = bool(re.search(r'/\d{4,}', path_lower))
        has_date_path = bool(re.search(r'/\d{4}/\d{1,2}', path_lower))

        return has_news_pattern or has_numeric_id or has_date_path

    def _clean_tree(self, tree: HtmlElement):
        """清理 DOM 树"""
        for elem in tree.xpath('//script | //style | //comment() | //noscript | //iframe'):
            if elem.getparent() is not None:
                elem.drop_tree()

    def _find_list_containers_by_xpath(self, tree: HtmlElement) -> List[HtmlElement]:
        """使用预定义 XPath 查找容器"""
        containers = []
        for xpath in self.LIST_CONTAINER_XPATHS:
            containers.extend(tree.xpath(xpath))
        return containers

    def _find_list_containers_by_heuristics(self, tree: HtmlElement) -> List[HtmlElement]:
        """使用启发式规则查找容器"""
        containers = []
        for elem in tree.xpath("//div | //ul | //section | //article"):
            class_id = self._get_class_id(elem)
            if self.REGEXPS["list_positive"].search(class_id):
                containers.append(elem)
        return containers

    def _get_class_id(self, elem: HtmlElement) -> str:
        """获取元素的 class 和 id 组合字符串"""
        return f"{elem.get('class', '')} {elem.get('id', '')}"

    def _get_text(self, elem: HtmlElement) -> str:
        """获取元素直接文本"""
        return (elem.text_content() or "").strip()

    def _get_clean_link_text(self, link: HtmlElement) -> str:
        """获取干净的链接文本"""
        text = link.text_content() or ""
        text = " ".join(text.split()).strip()
        text = re.sub(r'^[·•\-\*》►▶→]+\s*', '', text)
        text = re.sub(r'^[\(\[【]?\d{1,3}[\)\]】]?[\.、\)）]?\s*', '', text)
        text = re.sub(r'\s+\d{4}[-/]\d{1,2}[-/]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?)?$', '', text)
        return text.strip()


def extract_news_list(
    html: Union[str, bytes],
    base_url: str = "",
    content_type: Optional[str] = None
) -> List[dict]:
    """
    便捷函数：提取新闻列表
    """
    extractor = NewsListExtractor()
    items = extractor.extract(html, base_url, content_type=content_type)
    return [item.as_dict() for item in items]

