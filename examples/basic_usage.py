# -*- coding: utf-8 -*-
"""
NewsHarvest 基础使用示例

展示5个核心功能的使用方法
"""
import json
from newsharvest import (
    NewsHarvester,
    HarvesterConfig,
    fetch_news_list,
    fetch_article_content,
    harvest_news,
)


def example_1_fetch_list():
    """
    功能1: 传入列表页URL，采集并返回解析出的结果
    """
    print("=" * 60)
    print("功能1: 采集并解析新闻列表页")
    print("=" * 60)
    
    harvester = NewsHarvester()
    
    # 采集并解析列表页
    result = harvester.fetch_list("https://news.163.com/")
    with open("E:/mine/program/newsharvest/tests/test.txt", "w", encoding="utf-8") as f:
        json.dump(result.as_dict(), f, ensure_ascii=False, indent=4)
    if result.success:
        print(f"成功提取 {result.total_count} 条新闻:")
        for i, item in enumerate(result.items, 1):
            print(f"  {i}. {item.title}")
            print(f"     URL: {item.url}")
            print(f"     时间: {item.publish_time}")
    else:
        print(f"采集失败: {result.error}")
    
    harvester.close()
    print()


def example_2_parse_list_html():
    """
    功能2: 传入新闻列表页HTML，解析并返回新闻列表
    """
    print("=" * 60)
    print("功能2: 解析列表页 HTML")
    print("=" * 60)
    
    # 示例 HTML（实际使用时请替换为真实 HTML）
    html = """
    <html>
    <body>
        <div class="news-list">
            <div class="news-item">
                <a href="/news/2024/12/article1.html">
                    <h3>这是第一条新闻标题，内容很重要</h3>
                </a>
                <span class="time">2024-12-30 10:00</span>
            </div>
            <div class="news-item">
                <a href="/news/2024/12/article2.html">
                    <h3>这是第二条新闻标题，也很重要</h3>
                </a>
                <span class="time">2024-12-30 09:30</span>
            </div>
            <div class="news-item">
                <a href="/news/2024/12/article3.html">
                    <h3>这是第三条新闻标题，同样重要</h3>
                </a>
                <span class="time">2024-12-30 09:00</span>
            </div>
        </div>
    </body>
    </html>
    """
    
    harvester = NewsHarvester()
    items = harvester.parse_list(html, base_url="https://example.com")
    
    print(f"解析出 {len(items)} 条新闻:")
    for item in items:
        print(f"  - {item.title}")
        print(f"    URL: {item.url}")
        print(f"    时间: {item.publish_time}")
    
    harvester.close()
    print()


def example_3_fetch_article():
    """
    功能3: 传入新闻详情页URL，采集并解析详情页
    """
    print("=" * 60)
    print("功能3: 采集并解析新闻详情页")
    print("=" * 60)
    
    harvester = NewsHarvester()
    urls = ['https://www.163.com/dy/article/JTO42SOP0529AQIE.html']
    # 采集并解析详情页
    for url in urls:
        article = harvester.fetch_article(url)
        
        if article.success:
            # pass
            print(f"URL: {url} 标题: {article.title}")
            print(f"作者: {article.author}")
            print(f"时间: {article.publish_time}")
            print(f"内容长度: {len(article.content or '')} 字符")   
            if article.content:
                print(f"内容预览: {article.content}")
        else:
            print(f"采集失败:url={url} error={article.error}")
        
        harvester.close()
        print()


def example_4_parse_article_html():
    """
    功能4: 传入新闻详情页HTML，解析并返回文章内容
    """
    print("=" * 60)
    print("功能4: 解析详情页 HTML")
    print("=" * 60)
    
    # 示例 HTML
    html = """
    <html>
    <head>
        <title>重要新闻：Python 3.13 正式发布</title>
        <meta name="author" content="张三">
        <meta name="pubdate" content="2024-12-30">
    </head>
    <body>
        <article>
            <h1>Python 3.13 正式发布</h1>
            <div class="author">作者：张三</div>
            <div class="date">2024-12-30 10:00:00</div>
            <div class="content">
                <p>Python 3.13 今日正式发布，带来了多项重要改进。</p>
                <p>主要更新包括：性能优化、新语法特性、标准库增强等。</p>
                <p>开发团队表示，这是一次重大版本更新，建议所有用户升级。</p>
            </div>
        </article>
    </body>
    </html>
    """
    
    harvester = NewsHarvester()
    article = harvester.parse_article(html, url="https://example.com/news/123")
    
    print(f"标题: {article.title}")
    print(f"作者: {article.author}")
    print(f"时间: {article.publish_time}")
    print(f"内容: {article.content}")
    
    harvester.close()
    print()


def example_5_harvest():
    """
    功能5: 传入列表页URL，解析列表页并采集所有详情页
    """
    print("=" * 60)
    print("功能5: 完整采集流程（列表页 + 详情页）")
    print("=" * 60)
    
    # 进度回调
    def on_progress(current, total):
        print(f"  进度: {current}/{total}")
    
    # 文章采集回调
    def on_article(article):
        status = "✓" if article.success else "✗"
        title = (article.title or "无标题")[:30]
        print(f"  {status} {title}")
    
    config = HarvesterConfig(
        max_articles_per_list=5,  # 只采集前5篇
        request_delay=(1.0, 2.0),
        on_progress=on_progress,
        on_article_fetched=on_article,
    )
    
    harvester = NewsHarvester(config)
    
    # 完整采集流程
    result = harvester.harvest("https://news.sina.com.cn/")
    
    print(f"\n采集完成:")
    print(f"  列表页新闻数: {len(result.list_items)}")
    print(f"  成功采集: {result.success_count}")
    print(f"  采集失败: {result.failed_count}")
    
    harvester.close()
    print()


def example_convenience_functions():
    """
    使用便捷函数的示例
    """
    print("=" * 60)
    print("便捷函数使用示例")
    print("=" * 60)
    
    # 便捷函数1: 采集列表页
    print("\n1. fetch_news_list():")
    items = fetch_news_list("https://news.sina.com.cn/", timeout=10)
    print(f"   获取到 {len(items)} 条新闻")
    
    # 便捷函数2: 采集详情页
    print("\n2. fetch_article_content():")
    # article = fetch_article_content("https://news.example.com/article/123")
    # print(f"   标题: {article.get('title')}")
    print("   (需要有效的详情页 URL)")
    
    # 便捷函数3: 完整采集
    print("\n3. harvest_news():")
    # result = harvest_news("https://news.example.com", max_articles=5)
    # print(f"   采集了 {len(result.get('articles', []))} 篇文章")
    print("   (需要有效的列表页 URL)")
    
    print()


if __name__ == "__main__":
    # 运行示例（取消注释来运行）
    
    # example_1_fetch_list()
    # example_2_parse_list_html()
    example_3_fetch_article()
    # example_4_parse_article_html()
    # example_5_harvest()
    # example_convenience_functions()

