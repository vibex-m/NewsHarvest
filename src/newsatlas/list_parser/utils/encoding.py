# -*- coding: utf-8 -*-
"""
HTML编码检测与转换工具

支持多种编码检测策略：
1. HTTP响应头 Content-Type
2. HTML meta 标签声明
3. BOM (Byte Order Mark)
4. chardet/charset_normalizer 自动检测
"""

import re
from typing import Optional, Tuple

# 尝试导入编码检测库
try:
    import charset_normalizer
    CHARSET_NORMALIZER_AVAILABLE = True
except ImportError:
    CHARSET_NORMALIZER_AVAILABLE = False

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False


# 常见编码别名映射
ENCODING_ALIASES = {
    'gb2312': 'gbk',
    'gb_2312': 'gbk',
    'gb-2312': 'gbk',
    'chinese': 'gbk',
    'csiso58gb231280': 'gbk',
    'euc-cn': 'gbk',
    'euc_cn': 'gbk',
    'x-euc-cn': 'gbk',
    'iso-8859-1': 'latin-1',
    'latin1': 'latin-1',
    'ascii': 'utf-8',  # ASCII 是 UTF-8 的子集
}


def normalize_encoding(encoding: str) -> str:
    """
    标准化编码名称

    Args:
        encoding: 原始编码名称

    Returns:
        标准化后的编码名称
    """
    if not encoding:
        return 'utf-8'

    encoding = encoding.lower().strip()

    # 移除可能的引号
    encoding = encoding.strip('"\'')

    # 查找别名
    return ENCODING_ALIASES.get(encoding, encoding)


def detect_encoding_from_content_type(content_type: Optional[str]) -> Optional[str]:
    """
    从 HTTP Content-Type 头解析编码

    Args:
        content_type: HTTP响应的Content-Type头值

    Returns:
        检测到的编码，未找到返回None
    """
    if not content_type:
        return None

    # 解析 charset=xxx 部分
    match = re.search(r'charset\s*=\s*([^\s;,]+)', content_type, re.I)
    if match:
        return normalize_encoding(match.group(1))

    return None


def detect_encoding_from_html(html_bytes: bytes) -> Optional[str]:
    """
    从HTML内容检测编码

    检测策略：
    1. BOM检测
    2. meta charset 标签
    3. meta http-equiv Content-Type 标签
    4. XML声明

    Args:
        html_bytes: HTML字节内容

    Returns:
        检测到的编码，未找到返回None
    """
    # 1. BOM检测
    if html_bytes.startswith(b'\xef\xbb\xbf'):
        return 'utf-8'
    elif html_bytes.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif html_bytes.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    elif html_bytes.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32-be'
    elif html_bytes.startswith(b'\xff\xfe\x00\x00'):
        return 'utf-32-le'

    # 2. 尝试用ASCII/Latin-1解码前2048字节来查找meta标签
    # 这足以涵盖大多数网页的head部分
    head_bytes = html_bytes[:2048]

    try:
        head_text = head_bytes.decode('ascii', errors='ignore')
    except Exception:
        head_text = head_bytes.decode('latin-1', errors='ignore')

    # 3. meta charset="xxx"
    match = re.search(r'<meta[^>]+charset\s*=\s*["\']?([^"\'\s>]+)', head_text, re.I)
    if match:
        return normalize_encoding(match.group(1))

    # 4. meta http-equiv="Content-Type" content="text/html; charset=xxx"
    match = re.search(
        r'<meta[^>]+http-equiv\s*=\s*["\']?Content-Type["\']?[^>]+content\s*=\s*["\']?[^"\']*charset=([^"\'\s;>]+)',
        head_text, re.I
    )
    if match:
        return normalize_encoding(match.group(1))

    # 也检查顺序相反的情况
    match = re.search(
        r'<meta[^>]+content\s*=\s*["\']?[^"\']*charset=([^"\'\s;>]+)[^>]+http-equiv\s*=\s*["\']?Content-Type',
        head_text, re.I
    )
    if match:
        return normalize_encoding(match.group(1))

    # 5. XML声明 <?xml version="1.0" encoding="xxx"?>
    match = re.search(r'<\?xml[^>]+encoding\s*=\s*["\']([^"\']+)["\']', head_text, re.I)
    if match:
        return normalize_encoding(match.group(1))

    return None


def detect_encoding_by_library(html_bytes: bytes) -> Optional[str]:
    """
    使用第三方库检测编码

    优先使用 charset_normalizer（更准确），回退到 chardet

    Args:
        html_bytes: HTML字节内容

    Returns:
        检测到的编码，未找到返回None
    """
    # 只检测前10KB，提高速度
    sample = html_bytes[:10240]

    if CHARSET_NORMALIZER_AVAILABLE:
        try:
            result = charset_normalizer.detect(sample)
            if result and result.get('encoding'):
                return normalize_encoding(result['encoding'])
        except Exception:
            pass

    if CHARDET_AVAILABLE:
        try:
            result = chardet.detect(sample)
            if result and result.get('encoding'):
                confidence = result.get('confidence', 0)
                # 只在置信度较高时使用chardet结果
                if confidence > 0.7:
                    return normalize_encoding(result['encoding'])
        except Exception:
            pass

    return None


def decode_html(
    html_bytes: bytes,
    content_type: Optional[str] = None,
    fallback_encoding: str = 'utf-8'
) -> Tuple[str, str]:
    """
    智能解码HTML字节为字符串

    检测策略优先级：
    1. HTTP Content-Type 头
    2. HTML内容中的编码声明
    3. 第三方库自动检测
    4. 回退编码

    Args:
        html_bytes: HTML字节内容
        content_type: HTTP响应的Content-Type头（可选）
        fallback_encoding: 回退编码，默认utf-8

    Returns:
        (decoded_html, detected_encoding) 元组
    """
    detected_encoding = None

    # 1. 从Content-Type检测
    if content_type:
        detected_encoding = detect_encoding_from_content_type(content_type)

    # 2. 从HTML内容检测
    if not detected_encoding:
        detected_encoding = detect_encoding_from_html(html_bytes)

    # 3. 使用第三方库检测
    if not detected_encoding:
        detected_encoding = detect_encoding_by_library(html_bytes)

    # 4. 使用回退编码
    if not detected_encoding:
        detected_encoding = fallback_encoding

    # 尝试解码
    try:
        decoded = html_bytes.decode(detected_encoding)
        return decoded, detected_encoding
    except (UnicodeDecodeError, LookupError):
        pass

    # 如果检测到的编码失败，尝试常见编码
    common_encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1', 'cp1252']

    for encoding in common_encodings:
        if encoding == detected_encoding:
            continue
        try:
            decoded = html_bytes.decode(encoding)
            return decoded, encoding
        except (UnicodeDecodeError, LookupError):
            continue

    # 最后的回退：使用errors='replace'
    decoded = html_bytes.decode('utf-8', errors='replace')
    return decoded, 'utf-8'


def smart_decode_response(response) -> Tuple[str, str]:
    """
    智能解码 requests.Response 对象

    Args:
        response: requests.Response 对象

    Returns:
        (decoded_html, detected_encoding) 元组
    """
    content_type = response.headers.get('Content-Type', '')
    return decode_html(response.content, content_type)


# 便捷函数
def get_html_text(response) -> str:
    """
    从 requests.Response 获取正确编码的HTML文本

    Args:
        response: requests.Response 对象

    Returns:
        解码后的HTML字符串
    """
    text, _ = smart_decode_response(response)
    return text

