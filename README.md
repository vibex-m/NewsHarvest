# NewsAtlas 📰

[English](README_EN.md) | **简体中文**

**专注解决新闻列表页解析痛点**。

虽然目前市面上已有大量成熟的新闻**详情页**解析工具，但**列表页**数据的自动化解析一直是业界的空白和难题。**NewsAtlas 正是为了解决这一痛点而生**——它能智能识别并提取各种形态的新闻列表数据，填补了通用爬虫领域的最后一块拼图。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)


## ✨ 特性

- 🔍 **智能列表页解析** - 基于 DOM 热区聚类算法，自动识别新闻列表
- 📄 **高质量内容提取** - 基于 trafilatura，精准提取正文内容
- 🔗 **URL 相似度匹配** - 基于结构相似度，扩展发现更多新闻链接
- 🌐 **自动编码检测** - 支持 GBK、UTF-8 等多种编码自动识别
- ⚡ **简单易用** - 5 个核心功能，覆盖所有使用场景

## 📦 安装

使用 uv 安装（推荐）：

```bash
cd newsatlas
uv venv
uv pip install -e .
```

或使用 pip：

```bash
pip install -e .
```

## 🚀 快速开始

### 核心功能

```python
from newsatlas import NewsAtlas

atlas = NewsAtlas()

# 功能1: 采集并解析新闻列表页
result = atlas.fetch_list("https://news.example.com")
for item in result.items:
    print(item.title, item.url)

# 功能2: 直接解析列表页 HTML
items = atlas.parse_list(html_content, base_url="...")

# 功能3: 采集并解析新闻详情页
article = atlas.fetch_article("https://news.example.com/article/123")
print(article.title, article.content)

# 功能4: 直接解析详情页 HTML
article = atlas.parse_article(html_content)

# 功能5: 完整采集流程（列表+详情）
result = atlas.collect("https://news.example.com")
print(f"成功采集 {len(result.articles)} 篇文章")
```
atlas.close()

### 便捷函数

```python
from newsatlas import fetch_news_list, fetch_article_content, collect_news

# 采集新闻列表
items = fetch_news_list("https://news.example.com")

# 采集文章内容
article = fetch_article_content("https://news.example.com/article/123")

# 完整采集
result = collect_news("https://news.example.com", max_articles=20)
```

## 📖 API 文档

### NewsAtlas

主入口类，提供所有核心功能。

```python
from newsatlas import NewsAtlas, AtlasConfig

# 自定义配置
config = AtlasConfig(
    timeout=15,                    # 请求超时时间
    retry_times=2,                 # 重试次数
    request_delay=(1.0, 2.0),      # 请求间隔范围
    min_title_length=8,            # 最小标题长度
    max_articles_per_list=50,      # 每个列表页最多采集文章数
)

atlas = NewsAtlas(config)
```

### 数据模型

#### NewsItem

新闻列表项。

- `title`: 标题
- `url`: 链接
- `publish_time`: 发布时间（格式化字符串）
- `timestamp`: 时间戳

#### ArticleContent

新闻详情内容。

- `title`: 标题
- `content`: 正文内容
- `author`: 作者
- `publish_time`: 发布时间
- `raw_html`: 原始 HTML（可选）
- `success`: 是否成功
- `error`: 错误信息

#### AtlasResult

完整采集结果。

- `list_items`: 新闻列表 (`List[NewsItem]`)
- `articles`: 详情页内容列表 (`List[ArticleContent]`)
- `success_count`: 成功数量
- `failed_count`: 失败数量

## 🛠️ 便捷函数

```python
from newsatlas import fetch_news_list, fetch_article_content, collect_news

# 1. 仅获取列表
result = fetch_news_list("https://news.example.com")

# 2. 仅获取文章内容
article = fetch_article_content("https://news.example.com/article/123")

# 3. 完整采集
result = collect_news("https://news.example.com", max_articles=20)
```

### 回调函数

```python
def on_progress(current: int, total: int):
    """采集进度回调"""
    print(f"Progress: {current}/{total}")

def on_article_fetched(article: ArticleContent):
    """文章采集完成回调"""
    print(f"Fetched: {article.title}")

config = AtlasConfig(
    on_progress=on_progress,
    on_article_fetched=on_article_fetched,
)
```

## 🔧 高级用法

### 单独使用列表页解析器

```python
from newsatlas import NewsListExtractor, ListExtractorConfig

config = ListExtractorConfig(
    min_title_length=8,
    min_items_count=3,
    use_similarity_matching=True,
    similarity_threshold=0.65,
)

extractor = NewsListExtractor(config)
items = extractor.extract(html, base_url="https://...")
```

### 单独使用详情页解析器

```python
from newsatlas import parse_article

article = parse_article(
    html,
    url="https://...",
    include_tables=True,
    include_links=False,
)
```

### 自定义爬虫配置

```python
from newsatlas import WebCrawler, CrawlerConfig

config = CrawlerConfig(
    timeout=20,
    retry_times=3,
    user_agent="MyBot/1.0",
    headers={"Cookie": "..."},
)

crawler = WebCrawler(config)
html, error = crawler.fetch("https://...")
```

## 🏗️ 项目结构

```
newsatlas/
├── pyproject.toml          # 项目配置
├── README.md               # 文档
├── LICENSE                 # 许可证
├── src/
│   └── newsatlas/
│       ├── __init__.py     # 公开 API
│       ├── core.py         # 主入口类
│       ├── models.py       # 数据模型
│       ├── crawler.py      # 网页爬虫
│       ├── detail_parser.py # 详情页解析
│       └── list_parser/    # 列表页解析模块
│           ├── extractor.py
│           ├── matchers/   # URL 匹配算法
│           └── utils/      # 工具函数
└── examples/
    └── basic_usage.py      # 使用示例
```

## 🔬 技术原理

### 列表页解析原理

NewsAtlas 采用了一套混合策略算法（Hybrid Strategy Algorithm），结合了规则匹配、启发式评估和机器学习思想，确保在不同类型的网页上都能获得极高的识别率。核心逻辑包含以下 6 个层面：

1.  **多维评分机制 (Multi-dimensional Scoring)**
    系统会对页面中的每个潜在容器（`<div>`, `<ul>` 等）进行打分。评分维度包括：
    *   **链接密度**：正文列表通常有较高的链接文本比率。
    *   **标题特征**：由 `min_title_length` (默认 8) 和 `max_title_length` 控制，过滤过短或过长的非新闻链接。
    *   **路径深度一致性**：同一列表中的新闻链接通常具有相似的 URL 路径深度。
    *   **时间元素**：包含时间/日期的列表项会获得更高权重。

2.  **预定义规则库 (Pre-defined Rules)**
    内置了数十种常见的 **XPath** 和 **CSS Selector** 模式（如 `class="news-list"`, `id="post-list"`），优先匹配标准命名规范的列表容器。

3.  **DOM 热区聚类 (DOM Heatmap Clustering)**
    这是一种基于密度的结构学习算法：
    *   系统首先识别页面中所有符合新闻 URL 特征的“种子链接”。
    *   将这些种子链接在 DOM 树中点亮，形成“热点”。
    *   热度会向上传播，根据热点聚集密度自动圈定“热区容器”。这使得系统能识别没有任何语义 Class 名的裸 HTML 列表。

4.  **扩散边界算法 (Diffusion Boundary Algorithm)**
    在确定热区后，算法会从每个锚点向外扩散（向上寻找父节点），直到遇到相邻的新闻项边界。这解决了“一个 `<li>` 包含图片、标题、简介、时间”的复杂组合提取问题，能精准切分出完整的 NewsItem。

5.  **URL 结构相似度匹配 (Structure Similarity Matching)**
    系统分析种子链接的 URL 模式（如 `/2024/01/15/...`），利用 **Levenshtein 距离** 和 **路径特征向量**，在页面中找出所有结构相似的链接。即使某些链接不在主列表中（如滚动加载区），也能被召回。

6.  **智能时间解析**
    不依赖单一规则，而是混合使用：
    *   HTML `time` 标签和 `datetime` 属性。
    *   针对中文语境优化的正则匹配（支持“30分钟前”、“2024年1月1日”等多种格式）。
    *   能够从 URL 中自动提取日期信息作为补充。

### 详情页解析

基于 [trafilatura](https://github.com/adbar/trafilatura) 库，使用多种策略提取正文：
- HTML 语义标签识别
- 文本密度分析
- 样板文本过滤
- 元数据提取

## 📋 依赖

- Python >= 3.10
- lxml >= 4.9.0
- requests >= 2.28.0
- trafilatura >= 1.6.0
- dateparser >= 1.1.0
- charset-normalizer >= 3.0.0

## 📄 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

## 📢 测试源与反馈

本项目的开发测试主要基于 [seed.txt](seed.txt) 中列出的中文新闻网站。

由于网页结构千变万化，实际使用中难免遇到解析失败的情况（特别是列表页）。
**如果您发现某个网站无法正确解析，请务必提交 Issue 并附上网址，我会持续优化迭代引擎。**

## 🙌 致敬

本项目参考并借鉴了以下优秀开源项目的设计思想，特此致敬：

*   [readability](https://github.com/mozilla/readability) - Mozilla 的网页正文提取库，正文提取的鼻祖
*   [trafilatura](https://github.com/adbar/trafilatura) - Python 领域目前最先进/强大的正文提取库，NewsAtlas 的详情页解析依赖于它
*   [GeneralNewsExtractor](https://github.com/GeneralNewsExtractor/GeneralNewsExtractor) - 优秀的通用新闻抽取器
*   [GerapyAutoExtractor](https://github.com/Gerapy/GerapyAutoExtractor) - 优秀的新闻抽取器
*   [newspaper4k](https://github.com/AndyTheFactory/newspaper4k) - 经典 Python 文章提取库的现代化分支

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系

如有问题或建议，请提交 Issue。
