# -*- coding: utf-8 -*-
"""
链接上下文提取器 - 根据链接位置提取 title 和 time

V3 改进：集成 DOM 热区扩散算法，解决时间错误提取问题
"""

import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Set
from urllib.parse import urljoin

from lxml.html import HtmlElement

# 尝试导入智能日期解析库
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False

# 导入扩散边界模块
try:
    from .diffusion import DiffusionContextExtractor
    DIFFUSION_AVAILABLE = True
except ImportError:
    DIFFUSION_AVAILABLE = False


class LinkContextExtractor:
    """
    链接上下文提取器

    根据链接在 DOM 中的位置，提取对应的 title 和 publish_time
    每个链接独立分析，不依赖统一的结构模式
    
    V3 改进：
    - 集成 DOM 热区扩散算法
    - 解决时间从不相关区域错误提取的问题
    - 同一板块的重点展示+普通列表被正确归为一组
    """

    # 时间格式正则
    TIME_PATTERNS = [
        re.compile(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)'),
        re.compile(r'(\d{1,2}[-/]\d{1,2})(?!\d)'),
        re.compile(r'(\d{4}年\d{1,2}月\d{1,2}日)'),
        re.compile(r'(\d{1,2}月\d{1,2}日)'),
        re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)'),
        re.compile(r'(\d+\s*(?:分钟|分鐘|小时|小時|天|周|週|秒)\s*前)(?=\s|$|[，,。.!！?？\]\)）])'),
        re.compile(r'(\d+\s*(?:seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?)\s*(?:ago))(\b|(?=\s|$|[,.!?)\]]))', re.I),
        re.compile(r'(刚刚|剛 剛|今天|昨天|前天|just now|today|yesterday)', re.I),
    ]

    # 时间相关的 class/属性名
    TIME_CLASS_KEYWORDS = ['time', 'date', 'publish', 'posted', 'created', 'datetime', 'meta']

    def __init__(self, tree: HtmlElement, base_url: str = "", anchor_urls: Optional[Set[str]] = None):
        """
        Args:
            tree: 解析后的 HTML 树
            base_url: 基础 URL
            anchor_urls: 锚点 URL 集合（用于 DOM 热区扩散算法）
        """
        self.tree = tree
        self.base_url = base_url
        self.anchor_urls = anchor_urls or set()
        
        # 构建 URL -> 链接元素 的映射
        self._build_url_map()
        
        # 初始化扩散上下文提取器（V3 新增）
        self._diffusion_extractor = None
        if DIFFUSION_AVAILABLE and self.anchor_urls:
            try:
                self._diffusion_extractor = DiffusionContextExtractor(
                    tree, self.anchor_urls, base_url
                )
            except Exception:
                pass  # 降级到传统方法

    def _build_url_map(self):
        """构建 URL 到链接元素的映射"""
        self.url_to_elements: Dict[str, List[HtmlElement]] = {}

        for link in self.tree.xpath("//a[@href]"):
            href = link.get("href", "")

            # 转换为绝对 URL
            if self.base_url and not href.startswith(("http://", "https://")):
                full_url = urljoin(self.base_url, href)
            else:
                full_url = href

            if full_url not in self.url_to_elements:
                self.url_to_elements[full_url] = []
            self.url_to_elements[full_url].append(link)
    
    def set_anchor_urls(self, anchor_urls: Set[str]):
        """
        设置锚点 URL 集合并初始化扩散算法
        
        在提取完高置信度锚点后调用此方法，启用 V3 扩散边界算法
        
        Args:
            anchor_urls: 锚点 URL 集合
        """
        self.anchor_urls = anchor_urls
        
        if DIFFUSION_AVAILABLE and anchor_urls:
            try:
                self._diffusion_extractor = DiffusionContextExtractor(
                    self.tree, anchor_urls, self.base_url
                )
            except Exception:
                self._diffusion_extractor = None

    def extract_context(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        根据 URL 提取对应的 title, publish_time 和 timestamp

        Args:
            url: 详情页 URL

        Returns:
            (title, publish_time, timestamp)
        """
        elements = self.url_to_elements.get(url, [])

        if not elements:
            return None, None, None

        # 可能有多个相同 URL 的链接，选择最佳的
        best_title = None
        best_time = None
        best_timestamp = None
        best_title_score = 0

        for link in elements:
            title, title_score = self._extract_title_from_link(link)
            time_str = self._extract_time_from_context(link)

            # 选择得分最高的标题
            if title_score > best_title_score:
                best_title = title
                best_title_score = title_score
                best_time = time_str
            elif title_score == best_title_score and time_str and not best_time:
                # 得分相同但这个有时间
                best_time = time_str
        
        if best_time:
            best_timestamp = self._normalize_time(best_time)

        return best_title, best_time, best_timestamp

    def _normalize_time(self, time_str: str) -> Optional[int]:
        """
        将时间字符串标准化为东八区时间戳
        """
        if not time_str:
            return None
            
        try:
            # 1. 预处理
            time_str = time_str.strip()
            # 移除常见的无关前缀
            for prefix in ["发布于", "发表于", "更新于", "time:", "date:", "Updated:", "Posted:"]:
                 if time_str.lower().startswith(prefix.lower()):
                     time_str = time_str[len(prefix):].strip()
            
            # 统一繁体转简体 (针对 dateparser 可能不支持繁体单位的情况)
            time_str = time_str.replace('小時', '小时').replace('分鐘', '分钟').replace('週', '周')
            
            dt = None
            
            # 2. 使用 dateparser 解析 (如果可用)
            if DATEPARSER_AVAILABLE:
                dt = dateparser.parse(
                    time_str, 
                    settings={
                        'TIMEZONE': 'Asia/Shanghai',
                        'RETURN_AS_TIMEZONE_AWARE': True,
                        'PREFER_DAY_OF_MONTH': 'first' 
                    }
                )
            
            # 3. 回退逻辑
            if not dt:
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"]:
                    try:
                        dt = datetime.strptime(time_str, fmt)
                        tz = timezone(timedelta(hours=8))
                        dt = dt.replace(tzinfo=tz)
                        break
                    except ValueError:
                        continue
            
            if dt:
                if dt.tzinfo is None:
                    tz = timezone(timedelta(hours=8))
                    dt = dt.replace(tzinfo=tz)
                return int(dt.timestamp())
                
        except Exception:
            pass
            
        return None

    def _extract_title_from_link(self, link: HtmlElement) -> Tuple[Optional[str], int]:
        """
        从链接元素提取标题

        Returns:
            (title, score) - score 用于比较多个候选标题
        """
        # 策略1: 链接内的 h1/h2/h3/h4 标签（最高优先级）
        for tag, score in [('h1', 100), ('h2', 90), ('h3', 80), ('h4', 70)]:
            h_elem = link.find(f".//{tag}")
            if h_elem is not None:
                title = self._clean_text(h_elem.text_content())
                if title and len(title) >= 4:
                    return title, score

        # 策略2: 链接的 title 属性
        title_attr = link.get("title", "")
        if title_attr and len(title_attr) >= 4:
            return self._clean_text(title_attr), 60

        # 策略3: 链接的直接文本内容
        link_text = self._clean_text(link.text_content())
        if link_text and len(link_text) >= 4:
            return link_text, 55

        # 策略4: 查找直接父容器内的标题元素
        container = self._find_item_container(link)
        if container is not None:
            for tag, score in [('h2', 85), ('h3', 75), ('h4', 65)]:
                for child in container:
                    if child.tag == tag:
                        title = self._clean_text(child.text_content())
                        if title and len(title) >= 4:
                            return title, score
                    h_elem = child.find(f"./{tag}")
                    if h_elem is not None:
                        title = self._clean_text(h_elem.text_content())
                        if title and len(title) >= 4:
                            return title, score

        # 策略5: 向上查找更多层级
        title, score = self._extract_title_from_ancestors(link, max_depth=3)
        if title:
            return title, score

        return None, 0

    def _extract_title_from_ancestors(self, link: HtmlElement, max_depth: int = 3) -> Tuple[Optional[str], int]:
        """
        从链接的祖先元素中提取标题
        """
        parent = link.getparent()
        depth = 0

        while parent is not None and depth < max_depth:
            depth += 1
            
            parent_tag = parent.tag.lower() if parent.tag else ''
            parent_class = (parent.get('class') or '').lower()

            # 边界检查
            if parent_tag in ('article', 'section', 'main', 'body', 'ul', 'ol'):
                break
            
            if parent_tag == 'li':
                break
            
            if any(kw in parent_class for kw in ['list', 'news', 'items', 'feed', 'wrap', 'container']):
                break
            
            sibling_links = parent.xpath('./a') + parent.xpath('.//a')
            if len(set(sibling_links)) > 3:
                break

            for tag, base_score in [('h2', 82), ('h3', 72), ('h4', 62)]:
                for child in parent:
                    if child.tag == tag:
                        title = self._clean_text(child.text_content())
                        if title and len(title) >= 4:
                            adjusted_score = base_score - depth * 3
                            return title, max(adjusted_score, 35)

            parent = parent.getparent()

        return None, 0

    def _extract_time_from_context(self, link: HtmlElement) -> Optional[str]:
        """从链接的上下文中提取时间"""
        # V3 优先使用扩散边界算法
        if self._diffusion_extractor and self._diffusion_extractor.is_initialized():
            if link in self._diffusion_extractor.lit_elements:
                time_str = self._diffusion_extractor.extract_time_for_element(link)
                if time_str:
                    return time_str
                return None
        
        # 传统方法
        time_str = self._extract_time_from_link_internal(link)
        if time_str:
            return time_str
        
        time_str = self._extract_time_from_siblings(link)
        if time_str:
            return time_str
        
        container = self._find_item_container(link)
        if container is None:
            container = link.getparent()
            if container is None:
                return None
        return self._extract_time_from_node_context(container)
    
    def _extract_time_from_link_internal(self, link: HtmlElement) -> Optional[str]:
        """从链接内部提取时间"""
        for span in link.xpath('.//span'):
            span_text = (span.text_content() or '').strip()
            if span_text and 5 < len(span_text) < 25:
                if any(c.isdigit() for c in span_text) and any(c in span_text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(span_text)
                    if time_str:
                        return time_str
        
        for text in link.xpath('./text()'):
            text = (text or '').strip()
            if text and 5 < len(text) < 25:
                if any(c.isdigit() for c in text) and any(c in text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(text)
                    if time_str:
                        return time_str
        
        return None
    
    def _extract_time_from_siblings(self, link: HtmlElement) -> Optional[str]:
        """从链接的兄弟节点提取时间"""
        parent = link.getparent()
        if parent is None:
            return None
        
        try:
            link_index = list(parent).index(link)
        except ValueError:
            return None
        
        siblings = list(parent)
        
        for i in range(link_index + 1, min(link_index + 3, len(siblings))):
            sibling = siblings[i]
            time_str = self._extract_time_from_sibling_element(sibling)
            if time_str:
                return time_str
        
        for i in range(link_index - 1, max(link_index - 3, -1), -1):
            sibling = siblings[i]
            time_str = self._extract_time_from_sibling_element(sibling)
            if time_str:
                return time_str
        
        if link.tail:
            tail_text = link.tail.strip()
            if tail_text and 5 < len(tail_text) < 25:
                if any(c.isdigit() for c in tail_text) and any(c in tail_text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(tail_text)
                    if time_str:
                        return time_str
        
        return None
    
    def _extract_time_from_sibling_element(self, elem: HtmlElement) -> Optional[str]:
        """从兄弟元素中提取时间"""
        if elem.tag == 'a':
            return None
        
        if elem.tag == 'time':
            datetime_val = elem.get("datetime")
            if datetime_val:
                return datetime_val.strip()
            time_text = elem.text_content()
            if time_text:
                return time_text.strip()
        
        elem_class = (elem.get('class') or '').lower()
        for keyword in self.TIME_CLASS_KEYWORDS:
            if keyword in elem_class:
                time_str = self._extract_time_from_text(elem.text_content())
                if time_str:
                    return time_str
        
        if elem.tag in ('span', 'em', 'i', 'small', 'time', 'div', 'p'):
            elem_text = (elem.text_content() or '').strip()
            if elem_text and 5 < len(elem_text) < 25:
                if any(c.isdigit() for c in elem_text) and any(c in elem_text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(elem_text)
                    if time_str:
                        return time_str
        
        return None

    def _extract_time_from_node_context(self, container: HtmlElement) -> Optional[str]:
        """从节点及其上下文中提取时间"""
        
        time_elem = container.find(".//time")
        if time_elem is not None:
            datetime_val = time_elem.get("datetime")
            if datetime_val:
                return datetime_val.strip()
            time_text = time_elem.text_content()
            if time_text:
                return time_text.strip()

        for keyword in self.TIME_CLASS_KEYWORDS:
            for elem in container.xpath(f'.//*[contains(@class, "{keyword}")]'):
                time_str = self._extract_time_from_text(elem.text_content())
                if time_str:
                    return time_str

        for span in container.xpath('.//span'):
            span_text = (span.text_content() or '').strip()
            if span_text and 5 < len(span_text) < 25:
                if any(c.isdigit() for c in span_text) and any(c in span_text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(span_text)
                    if time_str:
                        return time_str

        container_text = " ".join([t.strip() for t in container.xpath('.//text()[not(ancestor::a)]') if t and t.strip()])
        time_str = self._extract_time_from_text(container_text)
        if time_str:
            return time_str
        
        link_texts = container.xpath('.//a//text()')
        for text in link_texts:
            text = (text or '').strip()
            if text and 5 < len(text) < 25:
                if any(c.isdigit() for c in text) and any(c in text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(text)
                    if time_str:
                        return time_str

        parent = container.getparent()
        for _ in range(2):
            if parent is None:
                break
            
            child_links = parent.xpath('.//a[@href]')
            if len(child_links) > 3:
                break
            
            time_elem = parent.find(".//time")
            if time_elem is not None:
                datetime_val = time_elem.get("datetime")
                if datetime_val:
                    return datetime_val.strip()
                time_text = time_elem.text_content()
                if time_text:
                    return time_text.strip()
            
            for keyword in self.TIME_CLASS_KEYWORDS:
                for elem in parent.xpath(f'.//*[contains(@class, "{keyword}")]'):
                    time_str = self._extract_time_from_text(elem.text_content())
                    if time_str:
                        return time_str
            
            parent = parent.getparent()
            
        return None

    def _find_item_container(self, link: HtmlElement) -> Optional[HtmlElement]:
        """查找包含链接的列表项容器"""
        parent = link.getparent()
        depth = 0

        while parent is not None and depth < 5:
            depth += 1

            if parent.tag in ('li', 'article', 'section', 'div'):
                grandparent = parent.getparent()
                if grandparent is not None:
                    siblings = [child for child in grandparent if child.tag == parent.tag]
                    if len(siblings) >= 2:
                        return parent

            parent = parent.getparent()

        return None

    def _extract_time_from_text(self, text: str) -> Optional[str]:
        """从文本中提取时间"""
        if not text:
            return None

        for pattern in self.TIME_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()

        return None

    def _clean_text(self, text: str) -> Optional[str]:
        """清理文本"""
        if not text:
            return None

        text = " ".join(text.split()).strip()
        text = re.sub(r'^[·•\-\*》►▶→]+\s*', '', text)
        text = re.sub(r'^[\(\[【]?\d{1,3}[\)\]】]?[\.、\)）]?\s*', '', text)
        text = re.sub(r"^\d+\s+(hrs?|hours?|mins?|minutes?|days?)\s+(ago\s+)?(?=[A-Z])", "", text, flags=re.I)
        text = re.sub(r'\s+\d{4}[-/]\d{1,2}[-/]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?)?$', '', text)

        return text.strip() if text else None

