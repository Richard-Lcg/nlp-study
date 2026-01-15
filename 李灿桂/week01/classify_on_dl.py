import torch
import torch.nn as nn
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
import jieba
import re

class TextClassificationModel(nn.Module):
    def __init__(self, input_size, num_classes):
        super(TextClassificationModel, self).__init__()
        self.linear = nn.Linear(input_size, num_classes)

    def forward(self, x, y=None):
        y_pred = self.linear(x)
        if y is not None:
            return nn.functional.cross_entropy(y_pred, y)
        else:
            return y_pred


class TextPreprocessor:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000)
        self.label_encoder = LabelEncoder()

    def preprocess_text(self, text):
        text = str(text)
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        words = jieba.lcut(text)
        return ' '.join(words)

    def fit_transform(self, texts, labels=None):
        processed_texts = [self.preprocess_text(text) for text in texts]
        X = self.vectorizer.fit_transform(processed_texts).toarray()

        if labels is not None:
            y = self.label_encoder.fit_transform(labels)
            return torch.FloatTensor(X), torch.LongTensor(y)
        return torch.FloatTensor(X)

    def transform(self, texts):
        processed_texts = [self.preprocess_text(text) for text in texts]
        X = self.vectorizer.transform(processed_texts).toarray()
        return torch.FloatTensor(X)


def load_data_from_csv(csv_path):
    df = pd.read_csv(csv_path, sep='\t', header=None, names=['text', 'label'])
    return df['text'].tolist(), df['label'].tolist()


def evaluate(model, test_x, test_y):
    model.eval()
    correct, wrong = 0, 0
    with torch.no_grad():
        y_pred = model(test_x)
        for i in range(len(test_y)):
            if torch.argmax(y_pred[i]) == test_y[i]:
                correct += 1
            else:
                wrong += 1

    accuracy = correct / (correct + wrong)
    print(f"正确预测个数：{correct}, 正确率：{accuracy:.4f}")
    return accuracy


def train_model(csv_path, model_save_path="text_classification_model.pt"):
    texts, labels = load_data_from_csv(csv_path)

    preprocessor = TextPreprocessor()
    X, y = preprocessor.fit_transform(texts, labels)

    input_size = X.shape[1]
    num_classes = len(preprocessor.label_encoder.classes_)

    print(f"输入维度: {input_size}, 类别数: {num_classes}")
    print(f"类别标签: {list(preprocessor.label_encoder.classes_)}")

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 配置参数
    epoch_num = 50
    batch_size = 20
    learning_rate = 0.001

    # 建立模型
    model = TextClassificationModel(input_size, num_classes)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # 训练过程
    for epoch in range(epoch_num):
        model.train()
        total_loss = 0
        num_batches = len(X_train) // batch_size

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = start_idx + batch_size

            batch_x = X_train[start_idx:end_idx]
            batch_y = y_train[start_idx:end_idx]

            loss = model(batch_x, batch_y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / num_batches if num_batches > 0 else total_loss

        # 评估
        acc = evaluate(model, X_test, y_test)

        print(f"第{epoch + 1}轮 - 平均loss: {avg_loss:.4f}, 准确率: {acc:.4f}")

    # 保存模型和预处理器
    torch.save({
        'model_state_dict': model.state_dict(),
        'preprocessor': preprocessor,
        'input_size': input_size,
        'num_classes': num_classes
    }, model_save_path)

    print(f"模型已保存到: {model_save_path}")
    return model, preprocessor


def predict_from_input(model_path, input_text):
    """根据用户输入预测类别"""
    # 加载保存的模型和预处理器 - 添加 weights_only=False
    checkpoint = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)

    # 重新创建预处理器
    preprocessor = checkpoint['preprocessor']

    # 重新创建模型
    model = TextClassificationModel(
        checkpoint['input_size'],
        checkpoint['num_classes']
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # 预处理输入文本
    X = preprocessor.transform([input_text])

    # 预测
    with torch.no_grad():
        result = model(X)
        predicted_idx = torch.argmax(result[0]).item()
        predicted_label = preprocessor.label_encoder.inverse_transform([predicted_idx])[0]

        # 获取所有类别的概率
        probabilities = torch.softmax(result[0], dim=0)

        # print(f"输入文本: {input_text}")
        # print(f"预测类别: {predicted_label}")
        # print("所有类别概率:")
        # for idx, label in enumerate(preprocessor.label_encoder.classes_):
        #     prob = probabilities[idx].item()
        #     print(f"  {label}: {prob:.4f}")

        return predicted_label


def main():
    # 训练模型
    csv_path = "dataset.csv"  # CSV文件路径
    model_path = "text_classification_model.pt"

    print("开始训练模型...")
    model, preprocessor = train_model(csv_path, model_path)

    # 测试一些示例
    test_examples = [
        "帮我导航到天安门"
        # "明天北京的天气怎么样",
        # "播放一首周杰伦的歌",
        # "帮我设置明天早上8点的闹钟",
        # "有没有从上海到北京的火车票",
        # "我想看恐怖电影",
        # "我想去北京玩",
        # "我喜欢看综艺节目",
        # "今天的电影怎么样？",
        # "用小米音响开下电视",
        # "播放首歌放松下如何",
        # "今天是农历十一月二十七"
    ]

    print("\n测试示例预测:")
    for example in test_examples:
        predict_from_input(model_path, example)
        print("-" * 50)


if __name__ == "__main__":
    main()