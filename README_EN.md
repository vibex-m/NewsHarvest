# NewsAtlas 📰

**English** | [简体中文](README.md)

**Focusing on solving the pain point of news list page parsing.**

While there are many mature tools for parsing news **detail pages** in the market, automated parsing of **list page** data has always been a gap and a challenge in the industry. **NewsAtlas was born to solve this pain point**—it can intelligently identify and extract news list data of various forms, filling the last piece of the puzzle in the general crawler field.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## ✨ Features

- 🔍 **Intelligent List Parsing** - Based on DOM heatmap clustering algorithm, automatically identifying news lists
- 📄 **High-Quality Content Extraction** - Based on trafilatura, accurately extracting body content
- 🔗 **URL Similarity Matching** - Based on structural similarity, expanding to discover more news links
- 🌐 **Auto Encoding Detection** - Supports auto-identification of multiple encodings like GBK, UTF-8
- ⚡ **Easy to Use** - 5 core functions covering all usage scenarios

## 📦 Installation

Install using uv (Recommended):

```bash
cd newsatlas
uv venv
uv pip install -e .
```

Or using pip:

```bash
pip install -e .
```

## 🚀 Quick Start

### Core Functions

```python
from newsatlas import NewsHarvester

harvester = NewsHarvester()

# Feature 1: Fetch and parse news list page
result = harvester.fetch_list("https://news.example.com")
for item in result.items:
    print(f"{item.title} - {item.url}")

# Feature 2: Parse list page HTML
items = harvester.parse_list(html_content, base_url="https://...")

# Feature 3: Fetch and parse news detail page
article = harvester.fetch_article("https://news.example.com/article/123")
print(article.title, article.content)

# Feature 4: Parse detail page HTML
article = harvester.parse_article(html_content)

# Feature 5: Complete harvesting flow (List + Details)
result = harvester.harvest("https://news.example.com")
for article in result.articles:
    print(f"{article.title}: {len(article.content)} chars")

harvester.close()
```

### Convenience Functions

```python
from newsatlas import fetch_news_list, fetch_article_content, harvest_news

# Fetch news list
items = fetch_news_list("https://news.example.com")

# Fetch article content
article = fetch_article_content("https://news.example.com/article/123")

# Complete harvesting
result = harvest_news("https://news.example.com", max_articles=20)
```

## 📖 API Documentation

### NewsHarvester

The main entry class providing all core functions.

```python
from newsatlas import NewsHarvester, HarvesterConfig

# Custom configuration
config = HarvesterConfig(
    timeout=15,                    # Request timeout
    retry_times=2,                 # Retry times
    request_delay=(1.0, 2.0),      # Request delay range
    min_title_length=8,            # Minimum title length
    max_articles_per_list=50,      # Max articles per list page
)

harvester = NewsHarvester(config)
```

### Data Models

#### NewsItem

News list item:

```python
@dataclass
class NewsItem:
    title: str           # News title
    url: str             # News link
    publish_time: str    # Publish time (optional)
    timestamp: int       # Timestamp (optional)
```

#### ArticleContent

Article details:

```python
@dataclass
class ArticleContent:
    url: str              # Article link
    title: str            # Article title
    content: str          # Body content
    author: str           # Author
    publish_time: str     # Publish time
    source: str           # Source
    description: str      # Description
    categories: List[str] # Categories
    tags: List[str]       # Tags
    language: str         # Language
    success: bool         # Success status
    error: str            # Error message
```

## 🏗️ Project Structure

```
newsatlas/
├── pyproject.toml          # Project configuration
├── README.md               # Documentation (Chinese)
├── README_EN.md            # Documentation (English)
├── LICENSE                 # License
├── src/
│   └── newsatlas/
│       ├── __init__.py     # Public API
│       ├── harvester.py    # Main entry class
│       ├── models.py       # Data models
│       ├── crawler.py      # Web crawler
│       ├── detail_parser.py # Detail page parser
│       └── list_parser/    # List page parser module
│           ├── extractor.py
│           ├── matchers/   # URL matching algorithms
│           └── utils/      # Utility functions
└── examples/
    └── basic_usage.py      # Usage examples
```

## 🔬 Technical Principles

### List Page Parsing Principles

NewsAtlas employs a Hybrid Strategy Algorithm, combining rule matching, heuristic evaluation, and machine learning ideas to ensure high recognition rates across different types of web pages. The core logic includes the following 6 layers:

1.  **Multi-dimensional Scoring**
    The system scores each potential container (`<div>`, `<ul>`, etc.) on the page. Scoring dimensions include:
    *   **Link Density**: Body lists usually have a higher ratio of link text.
    *   **Title Features**: Controlled by `min_title_length` (default 8) and `max_title_length`, filtering out non-news links that are too short or too long.
    *   **Path Depth Consistency**: News links in the same list usually have similar URL path depths.
    *   **Time Elements**: List items containing time/dates get higher weights.

2.  **Pre-defined Rules**
    Built-in dozens of common **XPath** and **CSS Selector** patterns (e.g., `class="news-list"`, `id="post-list"`), prioritizing standard naming conventions for list containers.

3.  **DOM Heatmap Clustering**
    This is a density-based structure learning algorithm:
    *   The system first identifies all "seed links" in the page that match news URL characteristics.
    *   These seed links are lit up in the DOM tree, forming "hotspots".
    *   Heat propagates upwards, automatically defining "hotzone containers" based on hotspot clustering density. This allows the system to identify raw HTML lists without any semantic Class names.

4.  **Diffusion Boundary Algorithm**
    After determining the hotzone, the algorithm diffuses outwards from each anchor (looking up for parent nodes) until it meets the boundary of adjacent news items. This solves the complex combination extraction problem (e.g., an `<li>` containing image, title, intro, time), accurately slicing out complete NewsItems.

5.  **Structure Similarity Matching**
    The system analyzes the URL patterns of seed links (e.g., `/2024/01/15/...`), using **Levenshtein Distance** and **Path Feature Vectors** to find all structurally similar links on the page. Even if some links are not in the main list (e.g., in a scroll-loading area), they can be recalled.

6.  **Intelligent Time Parsing**
    Relies not on a single rule but a mix of:
    *   HTML `time` tags and `datetime` attributes.
    *   Regex matching optimized for contexts (supports "30 mins ago", "2024-01-01", etc.).
    *   Automatically extracting date information from URLs as a supplement.

### Detail Page Parsing

Based on the [trafilatura](https://github.com/adbar/trafilatura) library, using multiple strategies to extract body content:
- HTML semantic tag recognition
- Text density analysis
- Boilerplate text filtering
- Metadata extraction
- Metadata extraction

## 📢 Test Sources & Feedback

The development and testing of this project are mainly based on Chinese news websites listed in [seed.txt](seed.txt).

Due to the ever-changing structure of web pages, parsing failures (especially for list pages) are inevitable in actual use.
**If you find a website that cannot be parsed correctly, please submit an Issue with the URL, and I will strictly optimize the iteration engine.**

## 🙌 Acknowledgements

This project references and draws inspiration from the design ideas of the following excellent open-source projects, paying tribute to:

*   [readability](https://github.com/mozilla/readability) - Mozilla's library for extracting article body, the forefather of content extraction.
*   [trafilatura](https://github.com/adbar/trafilatura) - Currently the most advanced/powerful content extraction library in Python, NewsAtlas relies on it for detail page parsing.
*   [GeneralNewsExtractor](https://github.com/GeneralNewsExtractor/GeneralNewsExtractor) - An excellent general news extractor.
*   [GerapyAutoExtractor](https://github.com/Gerapy/GerapyAutoExtractor) - An excellent project for automatic list page extraction.
*   [newspaper4k](https://github.com/AndyTheFactory/newspaper4k) - A modern branch of the classic Python article extraction library.

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## 🤝 Contribution

Issues and Pull Requests are welcome!

## 📮 Contact

If you have any questions or suggestions, please submit an Issue.
