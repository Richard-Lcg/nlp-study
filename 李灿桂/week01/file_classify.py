import pandas as pd
import jieba
from sklearn.feature_extraction.text import CountVectorizer # 词频统计
from sklearn.neighbors import KNeighborsClassifier # KNN
from openai import OpenAI
import classify_on_dl
import sys

# 将 classify_on_dl 中的 TextPreprocessor 和 TextClassificationModel 注册到当前模块
sys.modules['__main__'].TextPreprocessor = classify_on_dl.TextPreprocessor
sys.modules['__main__'].TextClassificationModel = classify_on_dl.TextClassificationModel

# 1. 读取csv文件
dataset = pd.read_csv("dataset.csv", sep="\t", header=None, nrows=1000)
# 2. 切割每个句子，用jieba进行分词
cut_sentences = dataset[0].apply(lambda x: "".join(jieba.lcut(x)))
# 3. 创建Vector对象
vector = CountVectorizer()
# 4. 生成词表（每个分词对应一个索引值）
vector.fit(cut_sentences.values)
# 5. 词转向量
features = vector.transform(cut_sentences.values)
# 6. 传入向量数据和类型值的集合后，进行模型训练
model = KNeighborsClassifier()
model.fit(features, dataset[1].values)

client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    # https://bailian.console.aliyun.com/?tab=model#/api-key
    api_key="sk-4f1e293d69ce4611830cf4386ab45cb3", # 账号绑定，用来计费的

    # 大模型厂商的地址，阿里云
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

def text_calssify_using_ml(text: str) -> str:
    """
    文本分类（机器学习），输入文本完成类别划分
    """
    test_sentence = " ".join(jieba.lcut(text))
    test_feature = vector.transform([test_sentence])
    return model.predict(test_feature)[0]

def text_calssify_using_llm(text: str) -> str:
    """
    文本分类（大语言模型），输入文本完成类别划分
    """
    completion = client.chat.completions.create(
        model="qwen-max",  # 模型的代号

        messages=[
            {"role": "user", "content": f"""帮我进行文本分类：{text}

输出的类别只能从如下中进行选择， 除了下面的类别，切勿输出其他任何无关信息。
FilmTele-Play            
Video-Play               
Music-Play              
Radio-Listen           
Alarm-Update        
Travel-Query        
HomeAppliance-Control  
Weather-Query          
Calendar-Query      
TVProgram-Play      
Audio-Play       
Other             
"""},  # 用户的提问
        ]
    )
    return completion.choices[0].message.content
def text_calssify_dl(text: str) -> str:
    model_path = "text_classification_model.pt"
    return classify_on_dl.predict_from_input(model_path, text)

if __name__ == "__main__":
    # pandas 用来进行表格的加载和分析
    # numpy 从矩阵的角度进行加载和计算
    print("机器学习: ", text_calssify_using_ml("帮我导航到天安门"))
    print("大语言模型: ", text_calssify_using_llm("帮我导航到天安门"))
    print("深度学习: ", text_calssify_dl("帮我导航到天安门"))
