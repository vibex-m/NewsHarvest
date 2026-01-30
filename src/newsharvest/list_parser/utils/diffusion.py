# -*- coding: utf-8 -*-
"""
DOM 热区扩散算法 - 基于 DOM 位置的智能边界识别

核心思想：
1. 点亮节点：标记所有锚点 URL 对应的 <a> 元素
2. 热度传播：向上冒泡统计热度，每个节点的热度 = 子树中的亮点数
3. 热区识别：找到热度聚集的分叉点，每个分叉出去的热子树是一个热区
4. 组内扩散：在每个热区内执行扩散算法，边界在同热区的其他亮点处停止

优势：
- 不依赖 URL 结构相似度
- 同一板块的重点展示+普通列表会被正确归为一组
- 自动识别不同区域（主区域/侧边栏等）
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from lxml.html import HtmlElement


class DOMHeatmapClusterer:
    """
    DOM 热区聚类器
    
    将 DOM 树中位置相近的锚点聚类到同一热区
    """
    
    def __init__(self, tree: HtmlElement, lit_elements: Set[HtmlElement]):
        """
        Args:
            tree: DOM 树根节点
            lit_elements: 被点亮的 <a> 元素集合
        """
        self.tree = tree
        self.lit_elements = lit_elements
        self.heat_map: Dict[HtmlElement, int] = {}
        
    def build_heatmap(self) -> Dict[HtmlElement, int]:
        """构建热力图：计算每个节点的热度"""
        self.heat_map.clear()
        
        # 初始化：所有亮点热度为1
        for elem in self.lit_elements:
            self.heat_map[elem] = 1
        
        # 向上传播热度
        for elem in self.lit_elements:
            self._propagate_heat_up(elem)
        
        return self.heat_map
    
    def _propagate_heat_up(self, elem: HtmlElement):
        """从元素向上传播热度"""
        parent = elem.getparent()
        while parent is not None:
            if parent not in self.heat_map:
                self.heat_map[parent] = 0
            self.heat_map[parent] += 1
            parent = parent.getparent()
    
    def find_hot_zones(self, min_zone_size: int = 2) -> List[Tuple[HtmlElement, Set[HtmlElement]]]:
        """
        找到热区（热度聚集的分叉点）
        
        算法：
        1. 从根节点开始，沿着热度路径向下遍历
        2. 当一个节点有多个"热"子节点时，说明到达了分叉点
        3. 每个分叉出去的热子树就是一个热区
        
        Args:
            min_zone_size: 热区最小亮点数
            
        Returns:
            [(热区根节点, 该热区内的亮点元素集合), ...]
        """
        if not self.heat_map:
            self.build_heatmap()
        
        zones = []
        root = self.tree
        self._find_zones_recursive(root, zones, min_zone_size)
        
        return zones
    
    def _find_zones_recursive(self, node: HtmlElement, zones: List, min_size: int):
        """递归寻找热区"""
        if node not in self.heat_map:
            return
        
        node_heat = self.heat_map.get(node, 0)
        if node_heat < min_size:
            return
        
        # 找出所有"热"的子节点
        hot_children = []
        for child in node:
            child_heat = self.heat_map.get(child, 0)
            if child_heat >= 1:
                hot_children.append((child, child_heat))
        
        # 判断是否是分叉点
        if len(hot_children) == 0:
            # 叶子节点或无热子节点
            if node in self.lit_elements:
                lit_in_zone = {node}
                zones.append((node, lit_in_zone))
        elif len(hot_children) == 1:
            # 只有一个热子节点，继续向下
            self._find_zones_recursive(hot_children[0][0], zones, min_size)
        else:
            # 多个热子节点 = 分叉点！每个热子树是一个热区
            for child, child_heat in hot_children:
                if child_heat >= min_size:
                    lit_in_zone = self._collect_lit_elements(child)
                    if len(lit_in_zone) >= min_size:
                        zones.append((child, lit_in_zone))
                elif child_heat >= 1:
                    # 热度不够但有亮点，继续向下找
                    self._find_zones_recursive(child, zones, 1)
    
    def _collect_lit_elements(self, root: HtmlElement) -> Set[HtmlElement]:
        """收集子树中的所有亮点元素"""
        lit_in_subtree = set()
        for elem in root.iter():
            if elem in self.lit_elements:
                lit_in_subtree.add(elem)
        return lit_in_subtree


class DiffusionBoundaryFinder:
    """
    扩散边界查找器
    
    从锚点 <a> 元素出发，向上扩散找到边界
    边界停止条件：遇到同热区的其他锚点
    """
    
    def __init__(self, zone_anchors: Set[HtmlElement]):
        """
        Args:
            zone_anchors: 同一热区内的所有锚点元素
        """
        self.zone_anchors = zone_anchors
    
    def find_boundary(self, anchor: HtmlElement, 
                      max_depth: int = 10) -> Tuple[Optional[HtmlElement], Set[HtmlElement], int]:
        """
        从锚点向外扩散找到边界
        
        Args:
            anchor: 起始锚点元素
            max_depth: 最大扩散深度
            
        Returns:
            (boundary_root, boundary_elements, depth)
        """
        current = anchor
        parent = anchor.getparent()
        boundary_root = anchor
        depth = 0
        
        while parent is not None and depth < max_depth:
            depth += 1
            
            # 检查父节点的子树中是否包含同热区的其他锚点
            has_other_anchor = False
            for elem in parent.iter():
                if elem in self.zone_anchors and elem != anchor:
                    has_other_anchor = True
                    break
            
            if has_other_anchor:
                # 找到其他锚点，停止扩散
                break
            else:
                # 没有其他锚点，继续扩散
                boundary_root = parent
                current = parent
                parent = parent.getparent()
        
        # 收集边界内的所有元素
        boundary_elements = set()
        for elem in boundary_root.iter():
            boundary_elements.add(elem)
        
        return boundary_root, boundary_elements, depth


class DiffusionContextExtractor:
    """
    扩散上下文提取器
    
    使用 DOM 热区聚类 + 扩散边界算法提取链接的上下文信息
    """
    
    # 时间格式正则
    TIME_PATTERNS = [
        re.compile(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)'),
        re.compile(r'(\d{1,2}[-/]\d{1,2})(?!\d)'),
        re.compile(r'(\d{4}年\d{1,2}月\d{1,2}日)'),
        re.compile(r'(\d{1,2}月\d{1,2}日)'),
        re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)'),
        re.compile(r'(\d+\s*(?:分钟|小时|天|周|秒)\s*前)'),
        re.compile(r'(\d+\s*(?:seconds?|minutes?|hours?|days?|weeks?)\s*ago)', re.I),
        re.compile(r'(刚刚|今天|昨天|前天|just now|today|yesterday)', re.I),
    ]
    
    TIME_CLASS_KEYWORDS = ['time', 'date', 'publish', 'posted', 'created', 'datetime', 'meta']
    
    def __init__(self, tree: HtmlElement, anchor_urls: Set[str], base_url: str = ""):
        """
        Args:
            tree: DOM 树
            anchor_urls: 锚点 URL 集合
            base_url: 基础 URL
        """
        self.tree = tree
        self.anchor_urls = anchor_urls
        self.base_url = base_url
        
        # URL -> <a> 元素
        self.url_to_elements: Dict[str, List[HtmlElement]] = defaultdict(list)
        # 所有锚点 <a> 元素
        self.lit_elements: Set[HtmlElement] = set()
        # 热区信息
        self.zones: List[Tuple[HtmlElement, Set[HtmlElement]]] = []
        # 元素 -> 热区ID
        self.element_to_zone: Dict[HtmlElement, int] = {}
        # 元素 -> 边界信息
        self.element_boundaries: Dict[HtmlElement, Tuple[HtmlElement, Set[HtmlElement]]] = {}
        
        self._initialize()
    
    def _initialize(self):
        """初始化"""
        from urllib.parse import urljoin
        
        # 1. 构建 URL 到元素的映射
        for link in self.tree.xpath("//a[@href]"):
            href = link.get("href", "")
            
            if self.base_url and not href.startswith(("http://", "https://")):
                full_url = urljoin(self.base_url, href)
            else:
                full_url = href
            
            if full_url in self.anchor_urls:
                self.url_to_elements[full_url].append(link)
                self.lit_elements.add(link)
        
        if not self.lit_elements:
            return
        
        # 2. DOM 热区聚类
        clusterer = DOMHeatmapClusterer(self.tree, self.lit_elements)
        clusterer.build_heatmap()
        self.zones = clusterer.find_hot_zones(min_zone_size=2)
        
        # 3. 建立元素到热区的映射
        for zone_id, (zone_root, zone_elements) in enumerate(self.zones):
            for elem in zone_elements:
                self.element_to_zone[elem] = zone_id
        
        # 4. 为每个锚点计算扩散边界
        self._compute_boundaries()
    
    def _compute_boundaries(self):
        """为每个锚点计算扩散边界"""
        # 按热区分组处理
        zone_elements: Dict[int, Set[HtmlElement]] = defaultdict(set)
        for elem, zone_id in self.element_to_zone.items():
            zone_elements[zone_id].add(elem)
        
        # 对每个热区内的元素计算边界
        for zone_id, elements in zone_elements.items():
            boundary_finder = DiffusionBoundaryFinder(elements)
            for elem in elements:
                boundary_root, boundary_elems, _ = boundary_finder.find_boundary(elem)
                self.element_boundaries[elem] = (boundary_root, boundary_elems)
        
        # 处理未归入热区的单独元素
        uncovered = self.lit_elements - set(self.element_to_zone.keys())
        for elem in uncovered:
            # 单独元素使用有限深度的扩散
            boundary_root, boundary_elems = self._diffuse_with_limit(elem, max_depth=3)
            self.element_boundaries[elem] = (boundary_root, boundary_elems)
    
    def _diffuse_with_limit(self, anchor: HtmlElement, 
                            max_depth: int = 3) -> Tuple[HtmlElement, Set[HtmlElement]]:
        """有深度限制的扩散（用于单独的亮点）"""
        boundary_root = anchor
        parent = anchor.getparent()
        depth = 0
        
        while parent is not None and depth < max_depth:
            depth += 1
            boundary_root = parent
            parent = parent.getparent()
        
        boundary_elements = set()
        for elem in boundary_root.iter():
            boundary_elements.add(elem)
        
        return boundary_root, boundary_elements
    
    def extract_time_for_element(self, elem: HtmlElement) -> Optional[str]:
        """
        使用扩散边界提取元素对应的时间
        
        关键改进：只在扩散边界内查找时间，不会从不相关区域提取
        """
        boundary_info = self.element_boundaries.get(elem)
        if not boundary_info:
            return None
        
        boundary_root, boundary_elements = boundary_info
        
        # 策略0: 优先从链接自身内部提取时间
        if elem.tag == 'a':
            time_str = self._extract_time_from_link_internal(elem)
            if time_str:
                return time_str
            
            time_str = self._extract_time_from_siblings(elem, boundary_elements)
            if time_str:
                return time_str
        
        # 策略1: 查找 <time> 标签
        for time_elem in boundary_root.xpath(".//time"):
            if time_elem in boundary_elements:
                datetime_val = time_elem.get("datetime")
                if datetime_val:
                    return datetime_val.strip()
                time_text = time_elem.text_content()
                if time_text:
                    return time_text.strip()
        
        # 策略2: 查找有时间相关 class 的元素
        for keyword in self.TIME_CLASS_KEYWORDS:
            for found_elem in boundary_root.xpath(f'.//*[contains(@class, "{keyword}")]'):
                if found_elem in boundary_elements:
                    time_str = self._extract_time_from_text(found_elem.text_content())
                    if time_str:
                        return time_str
        
        # 策略2.5: 查找边界内的所有短文本 span 元素
        for span in boundary_root.xpath('.//span'):
            if span not in boundary_elements:
                continue
            span_text = (span.text_content() or '').strip()
            if span_text and 5 < len(span_text) < 25:
                if any(c.isdigit() for c in span_text) and any(c in span_text for c in ['-', '/', ':', '年', '月', '日']):
                    time_str = self._extract_time_from_text(span_text)
                    if time_str:
                        return time_str
        
        # 策略3: 在边界内的非链接文本中查找时间
        texts = []
        for be in boundary_elements:
            if be.tag != 'a' and be not in self.lit_elements:
                if be.text:
                    texts.append(be.text.strip())
                if be.tail:
                    texts.append(be.tail.strip())
        
        combined_text = " ".join(t for t in texts if t)
        time_str = self._extract_time_from_text(combined_text)
        if time_str:
            return time_str
        
        return None
    
    def _extract_time_from_siblings(self, link: HtmlElement, boundary_elements: Set[HtmlElement]) -> Optional[str]:
        """从链接的兄弟节点提取时间（在边界内）"""
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
            if sibling not in boundary_elements:
                continue
            time_str = self._extract_time_from_sibling_element(sibling)
            if time_str:
                return time_str
        
        for i in range(link_index - 1, max(link_index - 3, -1), -1):
            sibling = siblings[i]
            if sibling not in boundary_elements:
                continue
            time_str = self._extract_time_from_sibling_element(sibling)
            if time_str:
                return time_str
        
        parent = link.getparent()
        if parent is not None and parent in boundary_elements:
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
    
    def _extract_time_from_text(self, text: str) -> Optional[str]:
        """从文本中提取时间"""
        if not text:
            return None
        
        for pattern in self.TIME_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def get_url_element(self, url: str) -> Optional[HtmlElement]:
        """获取 URL 对应的第一个元素"""
        elements = self.url_to_elements.get(url, [])
        return elements[0] if elements else None
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return len(self.lit_elements) > 0

