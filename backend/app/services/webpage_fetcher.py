from typing import Optional
import httpx
from bs4 import BeautifulSoup


async def fetch_page_text(url: str, max_chars: int = 8000) -> str:
    """
    抓取网页 HTML 并提取正文文本，返回截断后的字符串。
    """
    if not url:
        return ""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return ""

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # 删除脚本和样式
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    # 优先提取 <article> 区域
    article = soup.find("article")
    if article:
        texts = article.stripped_strings
    else:
        ps = soup.find_all("p")
        if ps:
            texts = (p.get_text(strip=True) for p in ps)
        else:
            texts = soup.stripped_strings

    content = "\n".join(t for t in texts if t)
    if len(content) > max_chars:
        content = content[:max_chars]
    return content
