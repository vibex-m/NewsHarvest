# -*- coding: utf-8 -*-
"""
URL相似度匹配算法

基于类型的结构相似度计算，用于新闻列表页提取增强。
解决基于正则模式匹配过于刚性，以及传统字符串相似度无法处理Slug/标题类URL的问题。

核心思想：
1. 将URL路径解析为段(Segment)序列
2. 识别每个段的类型（STATIC, NUMBER, SLUG, HASH, MIXED, DATE）
3. 计算段类型序列的相似度，而非内容的直接相似度
4. 通过路径深度、前缀模式等特征区分详情页和专题页
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from urllib.parse import urlparse
from collections import Counter

# 导入页面类型分类器
try:
    from ..utils.url_page_type import is_article_url, PageType, classify_url
    URL_PAGE_TYPE_AVAILABLE = True
except ImportError:
    URL_PAGE_TYPE_AVAILABLE = False


class SegmentType(Enum):
    """URL路径段类型"""
    STATIC = "static"   # 静态段 (news, article)
    NUMBER = "number"   # 纯数字 (12345, 17)
    DATE = "date"       # 日期段 (2025-12, 2024-01-15)
    SLUG = "slug"       # 标题段 (man-bites-dog, deep-learning-guide)
    HASH = "hash"       # 哈希/UUID (a1b2c3d4, 550e8400-e29b)
    MIXED = "mixed"     # 其他混合内容 (content_123, node_456)
    EMPTY = "empty"     # 空段


# 常见的URL ID前缀模式（详情页特征）
DETAIL_PAGE_PREFIXES = {
    'content_', 'article_', 'news_', 'post_', 'story_',
    'detail_', 'item_', 'id_', 'p_', 'a_', 'n_',
}

# 专题/列表页前缀模式（非详情页特征）
NON_DETAIL_PREFIXES = {
    'node_', 'topic_', 'tag_', 'category_', 'cat_',
    'list_', 'index_', 'page_', 'channel_',
}


def is_high_confidence_detail_url(url: str) -> bool:
    """
    判断URL是否为高置信度的详情页链接（锚点URL）
    
    融合两种判定策略：
    1. URL 页面类型理论（语义判定）
    2. URL 结构特征分析（技术判定）
    """
    # 策略1：URL 页面类型理论
    if URL_PAGE_TYPE_AVAILABLE:
        try:
            result = classify_url(url)
            if result.page_type == PageType.ARTICLE and result.confidence >= 0.7:
                return True
            if result.page_type == PageType.INDEX and result.confidence >= 0.7:
                return False
        except:
            pass
    
    # 策略2：URL 结构特征分析
    parser = URLParser()
    comp = parser.parse(url)

    # 条件1: 路径深度 >= 2
    if comp.depth < 2:
        return False

    # 条件2: 不能有专题页前缀
    if comp.prefix_pattern and comp.prefix_pattern in NON_DETAIL_PREFIXES:
        return False

    # 条件3: 排除 index.html 或 index 结尾的页面
    if comp.path_segments:
        last_seg = comp.path_segments[-1].lower()
        if last_seg in ('index', 'default', 'home', 'main', 'list'):
            return False

    # 条件4: 必须有以下特征之一
    has_detail_feature = False
    
    if comp.has_date_segment:
        has_detail_feature = True
    
    if comp.prefix_pattern and comp.prefix_pattern in DETAIL_PAGE_PREFIXES:
        has_detail_feature = True

    for i, (seg, seg_type) in enumerate(zip(comp.path_segments, comp.segment_types)):
        if seg_type == SegmentType.NUMBER and len(seg) >= 5:
            has_detail_feature = True
            break
        
        if seg_type == SegmentType.HASH:
            has_detail_feature = True
            break
        
        if seg_type == SegmentType.MIXED:
            numbers = re.findall(r'\d+', seg)
            if any(len(n) >= 6 for n in numbers):
                has_detail_feature = True
                break
        
        if seg_type == SegmentType.SLUG and i == len(comp.path_segments) - 1:
            if comp.depth >= 3:
                has_detail_feature = True
                break
            elif i >= 2:
                static_before = sum(1 for t in comp.segment_types[:i] if t == SegmentType.STATIC)
                if static_before >= 2:
                    has_detail_feature = True
                    break

    return has_detail_feature


def filter_anchor_urls(urls: list) -> list:
    """
    从URL列表中筛选出高置信度的锚点URL

    双重过滤策略：
    1. 首先使用规则过滤出高置信度URL
    2. 然后使用聚类过滤，确保只保留主流模式的URL
    """
    rule_based = [url for url in urls if is_high_confidence_detail_url(url)]
    
    if len(rule_based) < 2:
        return filter_by_structure_clustering(urls)
    
    clustered = filter_by_structure_clustering(rule_based)
    
    if len(clustered) >= 2:
        return clustered
    
    return rule_based


def filter_by_structure_clustering(urls: list, min_cluster_ratio: float = 0.3) -> list:
    """
    基于URL结构聚类识别主流模式（增强版）
    """
    if len(urls) < 3:
        return urls

    parser = URLParser()
    url_features = {}
    url_to_comp = {}
    
    for url in urls:
        comp = parser.parse(url)
        url_to_comp[url] = comp
        
        template_parts = []
        for seg, seg_type in zip(comp.path_segments, comp.segment_types):
            if seg_type == SegmentType.STATIC:
                template_parts.append(seg.lower())
            else:
                template_parts.append(f"<{seg_type.value}>")
        
        template = "/".join(template_parts)
        feature = (template, comp.depth, comp.has_date_segment)
        
        if feature not in url_features:
            url_features[feature] = []
        url_features[feature].append(url)

    clusters = list(url_features.items())
    clusters.sort(key=lambda x: len(x[1]), reverse=True)

    if not clusters:
        return urls

    main_feature, main_urls = clusters[0]
    main_size = len(main_urls)
    
    if main_size < 2:
        return urls
    
    min_cluster_size = max(3, int(main_size * 0.1))
    
    result_urls = []
    accepted_templates = []
    
    for feature, cluster_urls in clusters:
        template, depth, has_date = feature
        
        if len(cluster_urls) >= min_cluster_size:
            has_high_confidence = any(
                is_high_confidence_detail_url(url) for url in cluster_urls
            )
            
            if has_high_confidence:
                result_urls.extend(cluster_urls)
                accepted_templates.append(template)
    
    for feature, cluster_urls in clusters:
        template, depth, has_date = feature
        
        if len(cluster_urls) >= min_cluster_size:
            continue
        
        for accepted_template in accepted_templates:
            if _templates_similar(template, accepted_template, threshold=0.7):
                result_urls.extend(cluster_urls)
                break
    
    return result_urls


def _templates_similar(template1: str, template2: str, threshold: float = 0.7) -> bool:
    """判断两个路径模板是否相似"""
    parts1 = template1.split("/")
    parts2 = template2.split("/")
    
    if not parts1 or not parts2:
        return False
    
    first1 = parts1[0]
    first2 = parts2[0]
    
    if not first1.startswith("<") and not first2.startswith("<"):
        if first1.lower() != first2.lower():
            return False
    
    if abs(len(parts1) - len(parts2)) > 1:
        return False
    
    min_len = min(len(parts1), len(parts2))
    
    matches = 0
    for p1, p2 in zip(parts1, parts2):
        if p1 == p2:
            matches += 1
        elif p1.startswith("<") and p2.startswith("<"):
            if p1 == p2:
                matches += 1
            else:
                matches += 0.5
    
    return matches / min_len >= threshold


@dataclass
class URLComponents:
    """解析后的URL组件"""
    url: str
    domain: str
    path_segments: List[str]
    segment_types: List[SegmentType]
    extension: str
    prefix_pattern: Optional[str] = None
    has_date_segment: bool = False

    @property
    def depth(self) -> int:
        return len(self.path_segments)

    @property
    def is_likely_detail_page(self) -> bool:
        if self.depth < 2:
            return False
        if self.has_date_segment:
            return True
        if self.prefix_pattern and self.prefix_pattern in DETAIL_PAGE_PREFIXES:
            return True
        return False

    @property
    def is_likely_topic_page(self) -> bool:
        if self.depth == 1 and self.prefix_pattern:
            if self.prefix_pattern in NON_DETAIL_PREFIXES:
                return True
        return False


class URLParser:
    """URL解析与特征提取器"""

    COMMON_STATIC_KEYWORDS = {
        'news', 'article', 'articles', 'story', 'stories', 'post', 'posts',
        'blog', 'daily', 'weekly', 'world', 'local', 'topic', 'tag',
        'category', 'section', 'archive', 'archives', 'content', 'detail',
        'index', 'view', 'show', 'list'
    }

    DATE_PATTERNS = [
        re.compile(r'^\d{4}-\d{2}$'),
        re.compile(r'^\d{4}-\d{2}-\d{2}$'),
        re.compile(r'^\d{4}/\d{2}$'),
        re.compile(r'^\d{4}/\d{2}/\d{2}$'),
    ]

    def __init__(self, sample_segments: Optional[List[str]] = None):
        self.known_static_segments = set(self.COMMON_STATIC_KEYWORDS)
        if sample_segments:
            counter = Counter(sample_segments)
            for seg, count in counter.items():
                if count >= 2:
                    self.known_static_segments.add(seg)

    def parse(self, url: str) -> URLComponents:
        """解析URL为结构化组件"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path

            ext = ""
            if "." in path:
                parts = path.rsplit(".", 1)
                if len(parts) > 1 and "/" not in parts[1]:
                    ext = parts[1].lower()
                    path = parts[0]

            segments = [s for s in path.split("/") if s]
            types = [self.classify_segment(s) for s in segments]
            prefix_pattern = self._extract_prefix_pattern(segments)
            has_date = SegmentType.DATE in types

            return URLComponents(
                url=url,
                domain=domain,
                path_segments=segments,
                segment_types=types,
                extension=ext,
                prefix_pattern=prefix_pattern,
                has_date_segment=has_date
            )
        except Exception:
            return URLComponents(url, "", [], [], "")

    def _extract_prefix_pattern(self, segments: List[str]) -> Optional[str]:
        """提取MIXED段的前缀模式"""
        for seg in segments:
            match = re.match(r'^([a-zA-Z]+_)\d+', seg)
            if match:
                return match.group(1).lower()
        return None

    def classify_segment(self, segment: str) -> SegmentType:
        """推断段类型"""
        if not segment:
            return SegmentType.EMPTY

        if segment.isdigit():
            return SegmentType.NUMBER

        for pattern in self.DATE_PATTERNS:
            if pattern.match(segment):
                return SegmentType.DATE

        if segment.lower() in self.known_static_segments:
            return SegmentType.STATIC

        if "-" in segment:
            alpha_count = sum(1 for c in segment if c.isalpha())
            if alpha_count / len(segment) > 0.5 and len(segment) > 5:
                return SegmentType.SLUG

        if any(c.isdigit() for c in segment) and any(c.isalpha() for c in segment):
            clean_seg = segment.replace('-', '').replace('_', '')
            if len(clean_seg) >= 8 and re.match(r'^[a-z0-9]+$', clean_seg, re.I):
                digit_ratio = sum(c.isdigit() for c in clean_seg) / len(clean_seg)
                if 0.2 <= digit_ratio <= 0.8:
                    return SegmentType.HASH

        if segment.isalpha() and len(segment) < 15:
            return SegmentType.STATIC

        return SegmentType.MIXED


@dataclass
class SimilarityResult:
    """相似度计算结果"""
    total_score: float
    structure_score: float
    content_score: float
    matched: bool
    details: Dict = field(default_factory=dict)


class URLSimilarityCalculator:
    """URL相似度计算器"""

    def __init__(self,
                 weights: Dict[str, float] = None,
                 threshold: float = 0.6,
                 max_depth_diff: int = 1):
        self.weights = weights or {
            'structure': 0.8,
            'content': 0.2
        }
        self.threshold = threshold
        self.max_depth_diff = max_depth_diff

    def calculate(self, url1_comps: URLComponents, url2_comps: URLComponents) -> SimilarityResult:
        """计算两个URL组件对象的相似度"""
        if not self._is_same_root_domain(url1_comps.domain, url2_comps.domain):
            return SimilarityResult(0.0, 0.0, 0.0, False, {'reason': 'domain_mismatch'})

        depth_diff = abs(url1_comps.depth - url2_comps.depth)
        if depth_diff > self.max_depth_diff:
            return SimilarityResult(0.0, 0.0, 0.0, False, {
                'reason': 'depth_mismatch',
                'depth1': url1_comps.depth,
                'depth2': url2_comps.depth
            })

        if url1_comps.is_likely_detail_page and url2_comps.is_likely_topic_page:
            return SimilarityResult(0.0, 0.0, 0.0, False, {'reason': 'type_mismatch'})
        if url1_comps.is_likely_topic_page and url2_comps.is_likely_detail_page:
            return SimilarityResult(0.0, 0.0, 0.0, False, {'reason': 'type_mismatch'})

        if url1_comps.prefix_pattern and url2_comps.prefix_pattern:
            if url1_comps.prefix_pattern != url2_comps.prefix_pattern:
                return SimilarityResult(0.0, 0.0, 0.0, False, {
                    'reason': 'prefix_mismatch',
                    'prefix1': url1_comps.prefix_pattern,
                    'prefix2': url2_comps.prefix_pattern
                })

        struct_score = self._calculate_structure_score(
            url1_comps.segment_types,
            url2_comps.segment_types,
            url1_comps.path_segments,
            url2_comps.path_segments
        )

        content_score = self._calculate_content_score(url1_comps, url2_comps)

        if url1_comps.extension != url2_comps.extension:
            struct_score *= 0.8

        total_score = (
            struct_score * self.weights['structure'] +
            content_score * self.weights['content']
        )

        return SimilarityResult(
            total_score=total_score,
            structure_score=struct_score,
            content_score=content_score,
            matched=total_score >= self.threshold,
            details={
                'url1': url1_comps.url,
                'url2': url2_comps.url
            }
        )

    def _is_same_root_domain(self, domain1: str, domain2: str) -> bool:
        """检查是否为同根域名"""
        parts1 = domain1.split('.')
        parts2 = domain2.split('.')

        if len(parts1) >= 2 and len(parts2) >= 2:
            return parts1[-2:] == parts2[-2:]
        return domain1 == domain2

    def _calculate_structure_score(self,
                                   types1: List[SegmentType],
                                   types2: List[SegmentType],
                                   segs1: List[str] = None,
                                   segs2: List[str] = None) -> float:
        """计算类型序列相似度"""
        if not types1 and not types2:
            return 1.0
        if not types1 or not types2:
            return 0.0

        len1, len2 = len(types1), len(types2)
        min_len = min(len1, len2)
        max_len = max(len1, len2)

        matches = 0.0
        first_static_checked = False
        
        for i in range(min_len):
            t1, t2 = types1[i], types2[i]

            if t1 == t2:
                if t1 == SegmentType.STATIC and segs1 and segs2:
                    if segs1[i].lower() == segs2[i].lower():
                        matches += 1.0
                    else:
                        if not first_static_checked:
                            return 0.0
                        matches += 0.0
                    first_static_checked = True
                else:
                    matches += 1.0

            elif t1 == SegmentType.DATE and t2 == SegmentType.DATE:
                matches += 1.0
            elif t1 == SegmentType.SLUG and t2 == SegmentType.MIXED:
                matches += 0.5
            elif t1 == SegmentType.MIXED and t2 == SegmentType.SLUG:
                matches += 0.5
            elif t1 == SegmentType.NUMBER and t2 == SegmentType.MIXED:
                matches += 0.3
            elif t1 == SegmentType.MIXED and t2 == SegmentType.NUMBER:
                matches += 0.3

        score = matches / max_len
        return score

    def _calculate_content_score(self,
                                 comp1: URLComponents,
                                 comp2: URLComponents) -> float:
        """计算内容相似度"""
        segs1, types1 = comp1.path_segments, comp1.segment_types
        segs2, types2 = comp2.path_segments, comp2.segment_types

        static_indices1 = [i for i, t in enumerate(types1) if t == SegmentType.STATIC]
        static_indices2 = [i for i, t in enumerate(types2) if t == SegmentType.STATIC]

        if not static_indices1 and not static_indices2:
            if comp1.prefix_pattern and comp2.prefix_pattern:
                return 1.0 if comp1.prefix_pattern == comp2.prefix_pattern else 0.0
            if comp1.has_date_segment and comp2.has_date_segment:
                return 0.8
            return 0.5

        static1 = [segs1[i].lower() for i in static_indices1]
        static2 = [segs2[i].lower() for i in static_indices2]

        common = set(static1) & set(static2)
        union = set(static1) | set(static2)

        if not union:
            return 0.0

        return len(common) / len(union)


class URLSimilarityMatcher:
    """批量URL相似度匹配器"""
    
    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
        self.calculator = URLSimilarityCalculator(threshold=threshold)
        
    def find_similar(self, 
                    sample_urls: List[str], 
                    candidate_urls: List[str]) -> List[Tuple[str, float]]:
        """从候选URL中找出与样本相似的URL"""
        if not sample_urls or not candidate_urls:
            return []
            
        all_segments = []
        for url in sample_urls:
            parts = urlparse(url).path.split('/')
            all_segments.extend([p for p in parts if p])
            
        parser = URLParser(sample_segments=all_segments)
        sample_comps = [parser.parse(url) for url in sample_urls]
        
        results = []
        for candid_url in candidate_urls:
            candid_comp = parser.parse(candid_url)
            
            max_score = 0.0
            for sample_comp in sample_comps:
                res = self.calculator.calculate(sample_comp, candid_comp)
                if res.total_score > max_score:
                    max_score = res.total_score
            
            if max_score >= self.threshold:
                results.append((candid_url, max_score))
                
        results.sort(key=lambda x: x[1], reverse=True)
        return results


def find_similar_urls(sample_urls: List[str], candidate_urls: List[str], threshold: float = 0.65) -> List[str]:
    """便捷函数：找出相似的URL"""
    matcher = URLSimilarityMatcher(threshold=threshold)
    results = matcher.find_similar(sample_urls, candidate_urls)
    return [url for url, score in results]

