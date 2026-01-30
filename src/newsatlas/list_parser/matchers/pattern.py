# -*- coding: utf-8 -*-
"""
URL模式学习器

根据已经识别出的新闻详情页URL样本，学习其模式特征，
然后用这些特征去匹配页面中其他遗漏的新闻URL
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from urllib.parse import urlparse


@dataclass
class URLPattern:
    """URL模式"""
    pattern_type: str  # 模式类型: 'path_structure', 'regex', 'domain_path'
    pattern: str  # 正则表达式或模式字符串
    confidence: float  # 置信度 (0-1)
    sample_count: int  # 支持该模式的样本数量
    description: str  # 模式描述
    
    def __repr__(self):
        return f"URLPattern(type={self.pattern_type}, confidence={self.confidence:.2f}, pattern={self.pattern})"


class URLPatternLearner:
    """
    URL模式学习器
    
    从给定的新闻URL样本中学习模式特征
    """
    
    def __init__(self, min_sample_ratio: float = 0.3, min_samples: int = 2):
        self.min_sample_ratio = min_sample_ratio
        self.min_samples = min_samples
        
    def learn_patterns(self, sample_urls: List[str]) -> List[URLPattern]:
        """从样本URL中学习模式"""
        if not sample_urls:
            return []
        
        patterns = []
        
        path_patterns = self._learn_path_structure_patterns(sample_urls)
        patterns.extend(path_patterns)
        
        segment_patterns = self._learn_path_segment_patterns(sample_urls)
        patterns.extend(segment_patterns)
        
        id_patterns = self._learn_id_patterns(sample_urls)
        patterns.extend(id_patterns)
        
        extension_patterns = self._learn_extension_patterns(sample_urls)
        patterns.extend(extension_patterns)
        
        domain_path_patterns = self._learn_domain_path_patterns(sample_urls)
        patterns.extend(domain_path_patterns)
        
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        return patterns
    
    def _learn_path_structure_patterns(self, urls: List[str]) -> List[URLPattern]:
        """学习路径结构模式"""
        patterns = []
        structure_counter = Counter()
        structure_to_samples = defaultdict(list)
        
        for url in urls:
            parsed = urlparse(url)
            path = parsed.path
            
            abstract_path = re.sub(r'\d{4}(?=[-/])', '{year}', path)
            abstract_path = re.sub(r'\d{1,2}(?=[-/])', '{month}', abstract_path)
            abstract_path = re.sub(r'\d{8}', '{date}', abstract_path)
            abstract_path = re.sub(r'\d{6,}', '{long_id}', abstract_path)
            abstract_path = re.sub(r'\d{3,5}', '{id}', abstract_path)
            
            structure_counter[abstract_path] += 1
            structure_to_samples[abstract_path].append(url)
        
        for structure, count in structure_counter.items():
            if count < self.min_samples:
                continue
            
            ratio = count / len(urls)
            if ratio < self.min_sample_ratio:
                continue
            
            regex_pattern = self._structure_to_regex(structure)
            
            patterns.append(URLPattern(
                pattern_type='path_structure',
                pattern=regex_pattern,
                confidence=ratio,
                sample_count=count,
                description=f"路径结构: {structure}"
            ))
        
        return patterns
    
    def _structure_to_regex(self, structure: str) -> str:
        """将抽象结构转换为正则表达式"""
        regex = re.escape(structure)
        
        regex = regex.replace(r'\{year\}', r'\d{4}')
        regex = regex.replace(r'\{month\}', r'\d{1,2}')
        regex = regex.replace(r'\{date\}', r'\d{8}')
        regex = regex.replace(r'\{long_id\}', r'\d{6,}')
        regex = regex.replace(r'\{id\}', r'\d{3,}')
        
        return regex
    
    def _learn_path_segment_patterns(self, urls: List[str]) -> List[URLPattern]:
        """学习路径段模式"""
        patterns = []
        segment_counter = Counter()
        
        for url in urls:
            parsed = urlparse(url)
            path = parsed.path
            
            segments = [s for s in path.split('/') if s and not s.isdigit()]
            
            for segment in segments:
                if '.' in segment or len(segment) > 50:
                    continue
                segment_counter[segment] += 1
        
        for segment, count in segment_counter.items():
            if count < self.min_samples:
                continue
            
            ratio = count / len(urls)
            if ratio < self.min_sample_ratio:
                continue
            
            regex_pattern = f"/{re.escape(segment)}/"
            
            patterns.append(URLPattern(
                pattern_type='path_segment',
                pattern=regex_pattern,
                confidence=ratio,
                sample_count=count,
                description=f"路径段: /{segment}/"
            ))
        
        return patterns
    
    def _learn_id_patterns(self, urls: List[str]) -> List[URLPattern]:
        """学习ID模式"""
        patterns = []
        id_length_counter = Counter()
        
        for url in urls:
            numbers = re.findall(r'\d+', url)
            for num in numbers:
                length = len(num)
                if length >= 4:
                    id_length_counter[length] += 1
        
        for length, count in id_length_counter.items():
            if count < self.min_samples:
                continue
            
            ratio = count / len(urls)
            if ratio < self.min_sample_ratio:
                continue
            
            regex_pattern = rf'\d{{{length}}}'
            
            patterns.append(URLPattern(
                pattern_type='id_pattern',
                pattern=regex_pattern,
                confidence=ratio,
                sample_count=count,
                description=f"包含{length}位数字ID"
            ))
        
        return patterns
    
    def _learn_extension_patterns(self, urls: List[str]) -> List[URLPattern]:
        """学习文件扩展名模式"""
        patterns = []
        extension_counter = Counter()
        
        for url in urls:
            parsed = urlparse(url)
            path = parsed.path
            
            if '.' in path:
                extension = path.split('.')[-1].lower()
                if len(extension) <= 10 and extension.isalnum():
                    extension_counter[extension] += 1
            else:
                extension_counter['NO_EXT'] += 1
        
        for ext, count in extension_counter.items():
            if count < self.min_samples:
                continue
            
            ratio = count / len(urls)
            if ratio < self.min_sample_ratio:
                continue
            
            if ext == 'NO_EXT':
                regex_pattern = r'(?<!\.html)(?<!\.htm)(?<!\.shtml)(?<!\.php)(?<!\.aspx?)$'
                description = "无文件扩展名"
            else:
                regex_pattern = rf'\.{re.escape(ext)}$'
                description = f"扩展名: .{ext}"
            
            patterns.append(URLPattern(
                pattern_type='extension',
                pattern=regex_pattern,
                confidence=ratio,
                sample_count=count,
                description=description
            ))
        
        return patterns
    
    def _learn_domain_path_patterns(self, urls: List[str]) -> List[URLPattern]:
        """学习域名+路径前缀组合模式"""
        patterns = []
        domain_prefix_counter = Counter()
        
        for url in urls:
            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path
            
            path_parts = [p for p in path.split('/') if p]
            if len(path_parts) >= 1:
                prefix = '/' + path_parts[0]
                key = f"{domain}{prefix}"
                domain_prefix_counter[key] += 1
        
        for key, count in domain_prefix_counter.items():
            ratio = count / len(urls)
            
            if ratio >= 0.5:
                regex_pattern = f"^https?://{re.escape(key)}"
                
                patterns.append(URLPattern(
                    pattern_type='domain_path',
                    pattern=regex_pattern,
                    confidence=min(ratio + 0.2, 1.0),
                    sample_count=count,
                    description=f"域名+路径前缀约束: {key}"
                ))
        
        return patterns


class URLPatternMatcher:
    """
    URL模式匹配器
    
    使用学习到的模式去匹配新的URL
    """
    
    def __init__(self, patterns: List[URLPattern], min_pattern_match: int = 1):
        self.patterns = patterns
        self.min_pattern_match = min_pattern_match
        
        self.compiled_patterns = []
        for pattern in patterns:
            try:
                compiled = re.compile(pattern.pattern)
                self.compiled_patterns.append((compiled, pattern))
            except re.error:
                continue
    
    def match_url(self, url: str) -> Tuple[bool, float, List[URLPattern]]:
        """判断URL是否匹配学习到的模式"""
        matched_patterns = []
        total_confidence = 0.0
        
        has_domain_path_pattern = any(
            pattern.pattern_type == 'domain_path' 
            for _, pattern in self.compiled_patterns
        )
        domain_path_matched = False
        
        for compiled_regex, pattern in self.compiled_patterns:
            if compiled_regex.search(url):
                matched_patterns.append(pattern)
                total_confidence += pattern.confidence
                
                if pattern.pattern_type == 'domain_path':
                    domain_path_matched = True
        
        if has_domain_path_pattern and not domain_path_matched:
            return False, 0.0, []
        
        is_match = len(matched_patterns) >= self.min_pattern_match
        confidence = total_confidence / len(matched_patterns) if matched_patterns else 0.0
        
        return is_match, confidence, matched_patterns
    
    def filter_urls(
        self, 
        candidate_urls: List[str], 
        min_confidence: float = 0.3
    ) -> List[Tuple[str, float, List[URLPattern]]]:
        """从候选URL列表中筛选出匹配的URL"""
        results = []
        
        for url in candidate_urls:
            is_match, confidence, matched_patterns = self.match_url(url)
            
            if is_match and confidence >= min_confidence:
                results.append((url, confidence, matched_patterns))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results


def enhance_news_extraction(
    initial_urls: List[str],
    all_page_urls: List[str],
    min_confidence: float = 0.3,
    min_pattern_match: int = 1
) -> List[str]:
    """
    增强新闻URL提取：基于已提取的URL学习模式，找出遗漏的URL
    """
    if not initial_urls:
        return []
    
    learner = URLPatternLearner()
    patterns = learner.learn_patterns(initial_urls)
    
    if not patterns:
        return initial_urls
    
    matcher = URLPatternMatcher(patterns, min_pattern_match=min_pattern_match)
    
    initial_urls_set = set(initial_urls)
    candidate_urls = [url for url in all_page_urls if url not in initial_urls_set]
    
    matched_results = matcher.filter_urls(candidate_urls, min_confidence=min_confidence)
    
    new_urls = [url for url, _, _ in matched_results]
    
    return initial_urls + new_urls

