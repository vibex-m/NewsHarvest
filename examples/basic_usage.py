# -*- coding: utf-8 -*-
"""
NewsAtlas 基础使用示例

展示5个核心功能的使用方法
"""
import json
from newsatlas import (
    NewsAtlas, 
    AtlasConfig,
    fetch_news_list, 
    fetch_article_content, 
    collect_news
)


def example_1_fetch_list():
    """
    功能1: 传入列表页URL，采集并返回解析出的结果
    """
    print("=" * 60)
    print("功能1: 采集并解析新闻列表页")
    print("=" * 60)
    # 1. 创建采集器
    atlas = NewsAtlas()
    
    # 采集并解析列表页
    result = atlas.fetch_list("https://news.163.com/")
    if result.success:
        print(f"成功提取 {result.total_count} 条新闻:")
        for i, item in enumerate(result.items, 1):
            if i > 5: break
            print(f"  {i}. {item.title}")
            print(f"     URL: {item.url}")
            print(f"     时间: {item.publish_time}")
    else:
        print(f"采集失败: {result.error}")
        
    # 关闭
    atlas.close()
    print()


def example_2_parse_list_html():
    """示例2: 解析新闻列表页 HTML"""
    print("\n=== 功能2: 解析列表页 HTML ===")
    
    html = """
    <html>
        <div class="news-list">
            <a href="/news/2024/12/article1.html">这是第一条新闻标题，内容很重要</a>
            <span class="date">2024-12-30 10:00</span>
        </div>
        <div class="news-item">
            <a href="/news/2024/12/article2.html">这是第一条新闻标题，内容很重要</a>
            <span class="time">09:30</span>
        </div>
        <li>
            <a href="/news/2024/12/article3.html">这是第一条新闻标题，内容很重要</a>
            <span class="time">09:00</span>
        </li>
    </html>
    """
    
    atlas = NewsAtlas()
    items = atlas.parse_list(html, base_url="https://example.com/news/")
    
    print(f"解析出 {len(items)} 条新闻:")
    for item in items:
        print(f"  - {item.title}")
        print(f"    URL: {item.url}")
        print(f"    时间: {item.publish_time}")
    
    print()


def example_3_fetch_article():
    """示例3: 采集并解析新闻详情页"""
    print("\n=== 功能3: 采集并解析新闻详情页 ===")
    
    atlas = NewsAtlas()
    urls = ['https://www.163.com/dy/article/JTO42SOP0529AQIE.html']
    # 采集并解析详情页
    for url in urls:
        print(f"URL: {url}", end=" ")
        article = atlas.fetch_article(url)
        if article.success:
            print(f"标题: {article.title}")
            print(f"作者: {article.author}")
            print(f"时间: {article.publish_time}")
            print(f"内容长度: {len(article.content) if article.content else 0} 字符")
            print(f"内容预览: {article.content[:200] if article.content else 'None'} ...")
        else:
            print(f"采集失败: {article.error}")
            
    atlas.close()
    print()


def example_4_parse_article_html():
    """示例4: 解析新闻详情页 HTML"""
    print("\n=== 功能4: 解析详情页 HTML ===")
    
    html = """
    <html>
        <h1>Python 3.13 正式发布</h1>
        <div class="meta">
            <span>作者：张三</span>
            <span>2024-12-30 10:00:00</span>
        </div>
        <div class="content">
            <p>Python 3.13 今日正式发布，带来了多项重要改进。</p>
            <p>主要更新包括：性能优化、新语法特性、标准库增强等。</p>
            <p>开发团队表示，这是一次重大版本更新，建议所有用户升级。</p>
        </div>
    </html>
    """
    
    atlas = NewsAtlas()
    article = atlas.parse_article(html, url="https://example.com/news/123")
    
    print(f"标题: {article.title}")
    print(f"作者: {article.author}")
    print(f"时间: {article.publish_time}")
    print(f"内容: {article.content}")
    
    print()


def example_5_collect():
    """示例5: 完整采集流程"""
    print("\n=== 功能5: 完整采集流程（列表页 + 详情页） ===")
    
    # 1. 定义进度回调
    def on_progress(current, total):
        print(f"  进度: {current}/{total}")
        
    # 2. 定义文章采集回调
    def on_article(article):
        status = "✓" if article.success else "✗"
        print(f"  {status} {article.title[:20]}...")

    # 3. 创建自定义配置的采集器
    config = AtlasConfig(
        max_articles_per_list=5,  # 仅采集5篇用于演示
        on_progress=on_progress,
        on_article_fetched=on_article,
    )
    
    atlas = NewsAtlas(config)
    
    # 完整采集流程
    result = atlas.collect("https://news.sina.com.cn/")
    
    print("\n采集完成:")
    print(f"  列表页新闻数: {len(result.list_items)}")
    print(f"  成功采集: {result.success_count}")
    print(f"  采集失败: {result.failed_count}")
    
    atlas.close()
    print()


def example_convenience_functions():
    """示例: 使用便捷函数"""
    print("\n=== 便捷函数使用示例 ===")
    
    # 1. 直接获取列表
    print("\n1. fetch_news_list():")
    try:
        result = fetch_news_list("https://news.163.com/")
        if result.success:
            print(f"   获取到 {result.total_count} 条新闻")
            if result.items:
                print(f"   第一条: {result.items[0].title}")
        else:
            print(f"   获取失败: {result.error}")
    except Exception as e:
        print(f"   Error: {e}")
        
    # 2. 直接获取文章
    print("\n2. fetch_article_content():")
    try:
        url = "https://www.163.com/news/article/KKHGJHG2000189FH.html"
        article = fetch_article_content(url)
        if article.success:
            print(f"   标题: {article.title}")
            print(f"   长度: {len(article.content) if article.content else 0}")
        else:
            print(f"   获取失败: {article.error}")
    except Exception as e:
        print(f"   Error: {e}")
            
    # 3. 完整采集
    print("\n3. collect_news():")
    try:
        result = collect_news("https://news.sina.com.cn/", max_articles=2)
        print(f"   成功采集: {len(result.articles)} 篇")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()


if __name__ == "__main__":
    # 运行示例（取消注释来运行）
    
    example_1_fetch_list()
    example_2_parse_list_html()
    example_3_fetch_article()
    example_4_parse_article_html()
    example_5_collect()
    example_convenience_functions()

