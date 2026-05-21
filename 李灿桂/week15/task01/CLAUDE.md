# 多模态 RAG 知识库系统 - 项目说明

## 项目目标
实现一个支持图文混排 PDF 文档的上传、解析、向量化存储和检索增强生成（RAG）的问答系统。用户上传文档后，系统自动解析成 Markdown 和图片，提取文本/图像向量存入 Milvus，随后用户可通过自然语言提问，系统检索相关图文片段，调用多模态大模型生成答案。

## 核心组件
| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `web_demo.py` | Streamlit 多页导航入口 | `streamlit run web_demo.py` |
| `web_page_upload.py` | 文件上传 + Kafka 生产者 | 由 Streamlit 自动调用 |
| `web_page_chat.py` | RAG 检索 + 对话 + 图片渲染 | 由 Streamlit 自动调用 |
| `offline_precess_worker.py` | Kafka 消费者，解析文档并向量化 | `python offline_precess_worker.py`（后台长期运行） |

## 环境依赖与配置

### 1. 安装 Python 包
```bash
pip install streamlit openai sentence-transformers pymilvus kafka-python pillow