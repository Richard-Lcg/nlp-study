---
name: multimodal-rag
description: 多模态 RAG 知识库问答技能。支持上传 PDF/DOCX/TXT 文档，自动解析并向量化，然后根据图文混合问题检索相关片段，生成多模态答案。

---

# 多模态 RAG 技能

## 使用场景

- 用户需要从包含图片、表格、公式的复杂文档中获取答案。
- 用户上传一篇技术报告、产品手册或学术论文，希望针对其中的图文内容提问。

## 触发条件

用户明确要求使用该技能，或当前对话需要处理多模态检索增强生成时，可主动调用 `@multimodal-rag`。

## 核心流程

### 1. 文档上传与解析

- 帮助用户在 Streamlit 界面（文件管理页）上传 PDF 文件。
- 确保 Kafka 消费者 `offline_precess_worker.py` 正在后台运行。
- 等待消费者处理完成（可检查 Milvus 集合中是否存在对应 `db_id` 的记录）。

### 2. 问答检索与生成

- 用户提问后，按照 `web_page_chat.py` 的逻辑：
  - 使用 BGE 编码问题 → 检索文本块（`text_vector`）
  - 同时可使用 CLIP 文本编码检索 `clip_text_vector` 或 `clip_image_vector`（可选）
  - 将检索到的内容（文本 + 图片链接）填充到 `rag_prompt` 模板中
  - 调用多模态大模型（如 Qwen-VL、GPT-4V 等）生成答案
- 如果回答中包含图片链接，需要展示图片（Streamlit 中用 `st.image` 或 `st.markdown` 渲染）。

### 3. 调试建议

- 检查 Milvus 命中结果：打印 `results` 中的 `text` 字段，确认相关片段被召回。
- 验证图片路径：`render_markdown_with_images` 函数依赖本地文件存在，确保 `processed/` 目录下有对应图片。
- 测试单一文件：可先用小型 PDF 验证全流程。

## 示例对话

```text
用户：@multimodal-rag 上传 `product_manual.pdf`，然后问“如何更换电池？”
助手：[指导用户通过文件管理页上传]  
      上传成功后，等待解析完成（约 1-2 分钟）。  
      提问后，助手根据检索到的图文步骤给出答案，并展示相应插图。
```
