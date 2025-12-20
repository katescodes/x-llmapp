import asyncio
from typing import List, Tuple

import numpy as np

from ..schemas.chat import Source
from .embedding.http_embedding_client import embed_texts
from .search_client import search_web
from .webpage_fetcher import fetch_page_text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    简单按字符切片，避免单块太长。
    """
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


async def build_rag_context(
    query: str,
    max_search_results: int = 5,
    max_chunks: int = 8,
) -> Tuple[str, List[Source]]:
    """
    完整 RAG 流程：
    1. 调用 SearXNG 搜索
    2. 抓取每个搜索结果的网页正文
    3. 文本切片 + 向量化
    4. 基于问题向量做相似度排序，选出最相关的若干片段
    5. 构造给 LLM 用的上下文 + 前端展示用的 Source 列表
    """
    search_results = await search_web(query, limit=max_search_results)

    # 1. 抓网页正文（并发）
    fetch_tasks = [fetch_page_text(r.url) for r in search_results.results]
    pages = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # 2. 构造 chunk 列表
    all_chunks: List[dict] = []
    for idx, (result, page) in enumerate(zip(search_results.results, pages)):
        if isinstance(page, Exception) or not page:
            text = result.snippet or ""
        else:
            text = str(page)

        for chunk in chunk_text(text):
            all_chunks.append(
                {
                    "doc_index": idx,
                    "title": result.title,
                    "url": result.url,
                    "text": chunk,
                }
            )

    # 如果没有 chunk，就退化为仅用搜索摘要
    if not all_chunks:
        context_lines: List[str] = []
        sources: List[Source] = []
        for i, r in enumerate(search_results.results, start=1):
            sources.append(
                Source(
                    id=i,
                    title=r.title,
                    url=r.url,
                    snippet=r.snippet,
                )
            )
            context_lines.append(
                f"[{i}] 标题: {r.title}\nURL: {r.url}\n摘要: {r.snippet}\n"
            )
        context_text = "\n".join(context_lines)
        return context_text, sources

    # 3. 向量化
    texts = [c["text"] for c in all_chunks]
    doc_vectors = await embed_texts(texts)
    query_vectors = await embed_texts([query])
    if not doc_vectors or not query_vectors:
        raise RuntimeError("Embedding 服务返回空向量，无法构建上下文")

    doc_embeddings_list = []
    valid_chunks: List[dict] = []
    for chunk, vec in zip(all_chunks, doc_vectors):
        dense = vec.get("dense")
        if dense:
            doc_embeddings_list.append(np.array(dense, dtype=float))
            valid_chunks.append(chunk)

    if not doc_embeddings_list:
        raise RuntimeError("Embedding 服务未返回 dense 向量数据")

    query_dense = query_vectors[0].get("dense")
    if not query_dense:
        raise RuntimeError("Embedding 服务未返回查询的 dense 向量")

    doc_embeddings = np.stack(doc_embeddings_list)
    query_embedding = np.array(query_dense, dtype=float)

    # 4. 相似度（点积 = 余弦，因为已归一化）
    scores = doc_embeddings @ query_embedding  # (N,)
    top_k = min(max_chunks, len(valid_chunks))
    top_indices = np.argsort(-scores)[:top_k]

    # 5. 构造上下文和 Source 列表
    context_lines: List[str] = []
    source_map: dict[str, Source] = {}  # url -> Source
    next_source_id = 1

    for _, idx in enumerate(top_indices, start=1):
        c = valid_chunks[int(idx)]
        url = c["url"]
        title = c["title"]
        text = c["text"]

        if url not in source_map:
            source_map[url] = Source(
                id=next_source_id,
                title=title,
                url=url,
                snippet=text[:200],
            )
            source_id = next_source_id
            next_source_id += 1
        else:
            source_id = source_map[url].id

        context_lines.append(
            f"[{source_id}] 标题: {title}\nURL: {url}\n内容片段:\n{text}\n"
        )

    context_text = "\n---\n".join(context_lines)
    sources = sorted(source_map.values(), key=lambda s: s.id)
    return context_text, sources


async def retrieve_context(query: str) -> str:
    """
    Placeholder for decision-mode RAG retrieval.
    Replace with your vector store / knowledge base lookup.
    """
    _ = query
    return ""