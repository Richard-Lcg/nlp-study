from pydantic import BaseModel, Field
import openai

# 初始化客户端（请替换为你的有效 API Key 和 Base URL）
client = openai.OpenAI(
    api_key="sk-4f1e293d69ce4611830cf4386ab45cb3",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 以阿里云灵积为例
)

class ExtractionAgent:
    """复用 04_Pydantic与Tools.py 中的智能体"""
    def __init__(self, model_name: str):
        self.model_name = model_name

    def call(self, user_prompt, response_model):
        messages = [{"role": "user", "content": user_prompt}]
        schema = response_model.model_json_schema()
        tools = [{
            "type": "function",
            "function": {
                "name": schema["title"],
                "description": schema.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": schema["properties"],
                    "required": schema.get("required", []),
                },
            }
        }]
        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        try:
            arguments = response.choices[0].message.tool_calls[0].function.arguments
            return response_model.model_validate_json(arguments)
        except Exception as e:
            print("提取失败：", e)
            print("原始返回：", response.choices[0].message)
            return None

# 定义翻译意图抽取模型
class TranslationRequest(BaseModel):
    """从用户请求中提取翻译相关信息"""
    source_language: str = Field(description="原始语言，例如：英语、中文、法语等")
    target_language: str = Field(description="目标语言，例如：中文、英语、日语等")
    text: str = Field(description="需要翻译的文本内容")

if __name__ == "__main__":
    agent = ExtractionAgent(model_name="qwen-plus")  # 可根据需要更换模型

    # 测试你提供的例子
    prompt = "帮我将good！翻译为中文"
    result = agent.call(prompt, TranslationRequest)
    print("提取结果：", result)

    # 输出示例：
    # 提取结果： source_language='英语' target_language='中文' text='good！'