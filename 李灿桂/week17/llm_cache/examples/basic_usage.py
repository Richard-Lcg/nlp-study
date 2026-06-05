"""语义缓存 + 嵌入缓存 + 对话管理 使用示例"""
import json
import time

from llm_cache import (
    CacheConfig,
    RedisClient,
    SemanticCache,
    EmbeddingCache,
    ConversationManager,
    SemanticRouter,
    VectorIndex,
    HybridQuery,
)


def demo_embedding_cache():
    """嵌入缓存示例"""
    print("=" * 50)
    print("嵌入缓存示例")
    print("=" * 50)

    redis = RedisClient()
    emb_cache = EmbeddingCache(redis, ttl=120)

    # 模拟第一次嵌入计算
    text = "今天天气怎么样？"
    mock_vector = [0.1] * 768  # 模拟的嵌入向量

    emb_cache.set(text, mock_vector, model_name="text-embedding-3")
    print(f"缓存设置成功: {text[:20]}...")

    # 第二次直接从缓存读取
    cached = emb_cache.get(text, model_name="text-embedding-3")
    if cached:
        print(f"缓存命中: 向量维度 = {len(cached)}")

    # 批量操作
    texts = ["你好", "再见", "谢谢"]
    batch_result = emb_cache.bulk_get(texts, model_name="text-embedding-3")
    print(f"批量获取: {len([r for r in batch_result if r])} / {len(texts)} 命中")

    print()


def demo_semantic_cache():
    """语义缓存示例"""
    print("=" * 50)
    print("语义缓存示例")
    print("=" * 50)

    redis = RedisClient()
    sem_cache = SemanticCache(redis, ttl=120, similarity_threshold=0.85)

    # 模拟嵌入函数
    def mock_embedding(text: str) -> list[float]:
        import hashlib
        digest = hashlib.md5(text.encode()).hexdigest()
        seed = int(digest[:8], 16)
        rng = __import__("random").Random(seed)
        return [rng.random() for _ in range(16)]

    # 缓存 LLM 响应
    question = "什么是机器学习？"
    answer = "机器学习是人工智能的一个分支，使计算机能够从数据中学习。"
    sem_cache.set(question, answer, embedding=mock_embedding(question))
    print(f"缓存设置: '{question}' -> '{answer[:20]}...'")

    # 语义相似的查询
    similar_question = "能解释一下机器学习是什么吗？"
    cached_answer = sem_cache.get(similar_question, embedding_fn=mock_embedding)
    if cached_answer:
        print(f"语义缓存命中: '{similar_question}' -> '{cached_answer[:20]}...'")
    else:
        print("语义缓存未命中（阈值过低或嵌入不够相似）")

    print()


def demo_conversation():
    """对话管理示例"""
    print("=" * 50)
    print("对话管理示例")
    print("=" * 50)

    redis = RedisClient()
    cm = ConversationManager(redis, ttl=300, max_turns=5)

    session_id = "user:001"

    # 添加多条消息
    cm.add_message(session_id, "user", "你好")
    cm.add_message(session_id, "assistant", "你好！有什么可以帮助你的？")
    cm.add_message(session_id, "user", "今天天气怎么样？")
    cm.add_message(session_id, "assistant", "今天天气晴朗，气温25°C。")

    # 获取历史
    history = cm.get_history(session_id)
    print(f"对话历史 ({len(history)} 条):")
    for msg in history:
        print(f"  [{msg['role']}]: {msg['content'][:30]}...")

    # 格式化为 LLM 消息
    llm_messages = cm.format_for_llm(session_id, system_prompt="你是一个助手")
    print(f"\nLLM 消息格式 ({len(llm_messages)} 条):")
    for msg in llm_messages:
        print(f"  {msg['role']}: {msg['content'][:30]}...")

    print()


def demo_semantic_router():
    """语义路由示例"""
    print("=" * 50)
    print("语义路由示例")
    print("=" * 50)

    # 模拟嵌入函数
    def mock_embedding(text: str) -> list[float]:
        import hashlib
        digest = hashlib.md5(text.encode()).hexdigest()
        seed = int(digest[:8], 16)
        rng = __import__("random").Random(seed)
        return [rng.random() for _ in range(16)]

    router = SemanticRouter(embedding_fn=mock_embedding, similarity_threshold=0.7)

    # 注册路由
    router.add_route(
        name="weather",
        description="查询天气相关的问题",
        examples=["今天热吗", "明天会下雨吗", "温度多少"],
    )
    router.add_route(
        name="faq",
        description="回答常见问题，关于产品使用",
        examples=["怎么注册", "密码忘了怎么办", "如何付款"],
    )

    print("已注册路由:")
    for r in router.list_routes():
        print(f"  - {r['name']}: {r['description']}")

    # 测试路由
    test_inputs = ["今天天气怎么样", "如何重置密码"]
    for text in test_inputs:
        result = router.route(text)
        if result:
            print(f"\n'{
                text}' -> 匹配路由: {result['name']} (score: {result['score']:.3f})")
        else:
            print(f"\n'{text}' -> 无匹配路由")

    print()


def demo_vector_and_hybrid():
    """向量索引与混合搜索示例"""
    print("=" * 50)
    print("向量索引与混合搜索示例")
    print("=" * 50)

    redis = RedisClient()
    index_name = "demo_idx"

    # 创建向量索引
    vindex = VectorIndex(redis, index_name, dimension=4, metric="COSINE", algorithm="FLAT")
    vindex.create_index()

    # 插入示例数据
    docs = [
        ("doc1", [0.1, 0.2, 0.3, 0.4], {"title": "机器学习入门", "category": "tech"}),
        ("doc2", [0.9, 0.8, 0.7, 0.6], {"title": "如何做宫保鸡丁", "category": "food"}),
        ("doc3", [0.15, 0.25, 0.35, 0.45], {"title": "深度学习基础", "category": "tech"}),
    ]
    for doc_id, vec, meta in docs:
        vindex.add_vector(doc_id, vec, meta)
    print(f"已插入 {len(docs)} 条向量数据")

    import time
    time.sleep(1)

    # 向量搜索
    query_vec = [0.12, 0.22, 0.32, 0.42]
    results = vindex.search(query_vec, top_k=2)
    print(f"\n向量搜索结果 (top-2):")
    for r in results:
        print(f"  key={r['key']}")

    # 混合查询
    hybrid = HybridQuery(redis, index_name)
    text_results = hybrid.hybrid_search(query_vec, "入门", top_k=3, vector_weight=0.7)
    print(f"\n混合搜索结果 (top-3):")
    for r in text_results:
        print(f"  key={r['key']} hybrid_score={r['hybrid_score']}")

    vindex.delete_index()
    print()


if __name__ == "__main__":
    demo_embedding_cache()
    demo_semantic_cache()
    demo_conversation()
    demo_semantic_router()
    demo_vector_and_hybrid()
    print("所有示例运行完成！")
