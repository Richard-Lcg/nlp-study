import asyncio
from dataclasses import dataclass
from typing import Literal
from openai import AsyncOpenAI
from agents import Agent, RunContextWrapper, Runner,set_default_openai_client,set_default_openai_api,set_tracing_disabled

set_default_openai_api("chat_completions")

custom_client = AsyncOpenAI(
    api_key="sk-4f1e293d69ce4611830cf4386ab45cb3",  # 建议将此密钥移入环境变量
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    max_retries=2,        # 增加重试次数，提高稳定性
)
# --- 3. 将我们定制的客户端设置为全局默认客户端 ---
set_default_openai_client(custom_client)
@dataclass
class TypeContext:
    tp: Literal['emmotion','entity-rg']

def executeJob(rwc:RunContextWrapper[TypeContext], agent: Agent[TypeContext]) -> str:
    c = rwc.context
    if c.tp == 'emmotion':
        return '你是一位情感分析专家，请分析用户的描述，判断此时用户的心情和状态'
    else:
        return '根据用户给出的句子，进行实体识别，列出句子中包含的实体'

agent = Agent(
    name='agent-assistant',
    instructions=executeJob,
    model='qwen-max'
)

async def main():
    # taks1 :情感分析
    print("情感分析：")
    input_msg1 = '这周面试了10家公司都没拿到offer，但是有一半通过了初试，只是复试被刷了，有些可惜，还好下周还约面了3个，继续加油'
    print(f'user:{input_msg1}')
    result1 = await Runner.run(agent,input_msg1,context=TypeContext(tp='emmotion'))
    print(f"assistant:{result1}")

    # taks2 :实体识别
    print("实体识别：")
    input_msg2 = '马云于2019年9月10日在杭州的阿里巴巴总部宣布退休，当天还捐赠了10亿元给桃花源生态保护基金会'
    print(f'user:{input_msg2}')
    result2 = await Runner.run(agent,input_msg2,context=TypeContext(tp='entity-rg'))
    print(f"assistant:{result2}")


if __name__ == "__main__":
    asyncio.run(main())

