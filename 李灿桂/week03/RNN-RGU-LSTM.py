import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
import numpy as np
import matplotlib.pyplot as plt

# 设置随机种子以保证可重复性
torch.manual_seed(42)
np.random.seed(42)

# 加载数据
dataset = pd.read_csv("dataset.csv", sep="\t", header=None)
texts = dataset[0].tolist()
string_labels = dataset[1].tolist()

# 创建标签映射
label_to_index = {label: i for i, label in enumerate(set(string_labels))}
numerical_labels = [label_to_index[label] for label in string_labels]
index_to_label = {i: label for label, i in label_to_index.items()}

# 创建字符映射
char_to_index = {'<pad>': 0}
for text in texts:
    for char in text:
        if char not in char_to_index:
            char_to_index[char] = len(char_to_index)
vocab_size = len(char_to_index)

max_len = 40
output_dim = len(label_to_index)


# 自定义数据集
class TextDataset(Dataset):
    def __init__(self, texts, labels, char_to_index, max_len):
        self.texts = texts
        self.labels = torch.tensor(labels, dtype=torch.long)
        self.char_to_index = char_to_index
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        indices = [self.char_to_index.get(char, 0) for char in text[:self.max_len]]
        indices += [0] * (self.max_len - len(indices))
        return torch.tensor(indices, dtype=torch.long), self.labels[idx]


# 划分训练集和测试集
full_dataset = TextDataset(texts, numerical_labels, char_to_index, max_len)
train_size = int(0.8 * len(full_dataset))
test_size = len(full_dataset) - train_size
train_dataset, test_dataset = random_split(full_dataset, [train_size, test_size])

# 创建数据加载器
batch_size = 32
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

print(f"训练集大小: {len(train_dataset)}, 测试集大小: {len(test_dataset)}")


# ==================== 1. RNN模型 ====================
class RNNClassifier(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim, num_layers=2):
        super(RNNClassifier, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.rnn = nn.RNN(
            embedding_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            nonlinearity='tanh'
        )
        self.fc = nn.Linear(hidden_dim, output_dim)
        self.num_layers = num_layers
        self.hidden_dim = hidden_dim

    def forward(self, x):
        embedded = self.embedding(x)
        rnn_out, hidden = self.rnn(embedded)
        last_time_step = rnn_out[:, -1, :]
        out = self.fc(last_time_step)
        return out


# ==================== 2. GRU模型 ====================
class GRUClassifier(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim, num_layers=2, dropout=0.1):
        super(GRUClassifier, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x)
        gru_out, hidden = self.gru(embedded)
        last_time_step = gru_out[:, -1, :]
        out = self.fc(last_time_step)
        return out


# ==================== 3. LSTM模型 ====================
class LSTMClassifier(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim, num_layers=2, dropout=0.1):
        super(LSTMClassifier, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.lstm = nn.LSTM(
            embedding_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x)
        lstm_out, (hidden, cell) = self.lstm(embedded)
        last_time_step = lstm_out[:, -1, :]
        out = self.fc(last_time_step)
        return out


# 训练和评估函数
def train_model(model, train_loader, test_loader, model_name, num_epochs=10, learning_rate=0.001):
    """训练模型并返回训练过程中的指标"""

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    train_losses = []
    train_accuracies = []
    test_accuracies = []

    print(f"\n{'=' * 50}")
    print(f"开始训练 {model_name}")
    print(f"{'=' * 50}")

    for epoch in range(num_epochs):
        # 训练阶段
        model.train()
        running_loss = 0.0
        correct_train = 0
        total_train = 0

        for inputs, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()

            # 梯度裁剪（特别是对RNN）
            if model_name == "RNN":
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            running_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total_train += labels.size(0)
            correct_train += (predicted == labels).sum().item()

        avg_train_loss = running_loss / len(train_loader)
        train_accuracy = 100 * correct_train / total_train

        # 测试阶段
        test_accuracy = evaluate_model(model, test_loader)

        train_losses.append(avg_train_loss)
        train_accuracies.append(train_accuracy)
        test_accuracies.append(test_accuracy)

        print(f"Epoch [{epoch + 1}/{num_epochs}] - "
              f"训练损失: {avg_train_loss:.4f}, "
              f"训练准确率: {train_accuracy:.2f}%, "
              f"测试准确率: {test_accuracy:.2f}%")

    return {
        'model_name': model_name,
        'model': model,
        'train_losses': train_losses,
        'train_accuracies': train_accuracies,
        'test_accuracies': test_accuracies,
        'final_train_accuracy': train_accuracies[-1],
        'final_test_accuracy': test_accuracies[-1]
    }


def evaluate_model(model, test_loader):
    """评估模型在测试集上的准确率"""
    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, labels in test_loader:
            outputs = model(inputs)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    return 100 * correct / total


# 超参数设置
embedding_dim = 64
hidden_dim = 128
num_layers = 2
num_epochs = 10
learning_rate = 0.001

# 初始化模型
models = {
    "RNN": RNNClassifier(vocab_size, embedding_dim, hidden_dim, output_dim, num_layers),
    "GRU": GRUClassifier(vocab_size, embedding_dim, hidden_dim, output_dim, num_layers),
    "LSTM": LSTMClassifier(vocab_size, embedding_dim, hidden_dim, output_dim, num_layers)
}

# 训练所有模型并收集结果
results = {}
for name, model in models.items():
    result = train_model(model, train_loader, test_loader, name, num_epochs, learning_rate)
    results[name] = result

# ==================== 精度对比分析 ====================
print(f"\n{'=' * 60}")
print("模型精度对比结果")
print(f"{'=' * 60}")

# 创建对比表格
print(f"\n{'模型':<10} {'最终训练准确率':<20} {'最终测试准确率':<20}")
print("-" * 50)
for name in ["RNN", "GRU", "LSTM"]:
    result = results[name]
    print(f"{name:<10} {result['final_train_accuracy']:<20.2f}% {result['final_test_accuracy']:<20.2f}%")

# 绘制对比图表
plt.figure(figsize=(15, 5))

# 1. 训练损失对比
plt.subplot(1, 3, 1)
for name in ["RNN", "GRU", "LSTM"]:
    plt.plot(results[name]['train_losses'], label=f"{name}")
plt.xlabel('Epoch')
plt.ylabel('Training Loss')
plt.title('Training Loss Comparison')
plt.legend()
plt.grid(True)

# 2. 训练准确率对比
plt.subplot(1, 3, 2)
for name in ["RNN", "GRU", "LSTM"]:
    plt.plot(results[name]['train_accuracies'], label=f"{name}")
plt.xlabel('Epoch')
plt.ylabel('Training Accuracy (%)')
plt.title('Training Accuracy Comparison')
plt.legend()
plt.grid(True)

# 3. 测试准确率对比
plt.subplot(1, 3, 3)
for name in ["RNN", "GRU", "LSTM"]:
    plt.plot(results[name]['test_accuracies'], label=f"{name}")
plt.xlabel('Epoch')
plt.ylabel('Test Accuracy (%)')
plt.title('Test Accuracy Comparison')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig('model_comparison.png', dpi=300, bbox_inches='tight')
plt.show()

# ==================== 详细分析报告 ====================
print(f"\n{'=' * 60}")
print("详细分析报告")
print(f"{'=' * 60}")

# 找到最佳模型
best_model_name = max(results.keys(), key=lambda x: results[x]['final_test_accuracy'])
best_model = results[best_model_name]['model']

print(f"\n1. 最佳模型: {best_model_name}")
print(f"   测试准确率: {results[best_model_name]['final_test_accuracy']:.2f}%")

print("\n2. 各模型相对性能:")
for name in ["RNN", "GRU", "LSTM"]:
    test_acc = results[name]['final_test_accuracy']
    train_acc = results[name]['final_train_accuracy']
    gap = train_acc - test_acc  # 过拟合程度

    print(f"   {name}:")
    print(f"     测试准确率: {test_acc:.2f}%")
    print(f"     训练-测试差距: {gap:.2f}% (差距越小，泛化能力越好)")
    if gap > 10:
        print(f"     ⚠️  可能过拟合")
    elif gap < 5:
        print(f"     ✅  泛化能力良好")

print("\n3. 模型选择建议:")
if results["GRU"]['final_test_accuracy'] > results["LSTM"]['final_test_accuracy']:
    print("   ✅ GRU在准确率和效率之间取得了更好的平衡")
else:
    print("   ✅ LSTM取得了最高准确率，但训练可能更慢")

if results["RNN"]['final_test_accuracy'] < 70:
    print("   ⚠️  RNN表现不佳，可能不适合此任务")

# ==================== 单个样本预测测试 ====================
print(f"\n{'=' * 60}")
print("单个样本预测测试")
print(f"{'=' * 60}")

test_samples = [
    "帮我导航到北京",
    "查询明天北京的天气",
    "播放周杰伦的音乐",
    "打开空调",
    "今天有什么新闻"
]


def predict_with_all_models(text, models_dict, char_to_index, max_len, index_to_label):
    """用所有模型预测同一个样本"""
    indices = [char_to_index.get(char, 0) for char in text[:max_len]]
    indices += [0] * (max_len - len(indices))
    input_tensor = torch.tensor(indices, dtype=torch.long).unsqueeze(0)

    predictions = {}
    for name, model in models_dict.items():
        model.eval()
        with torch.no_grad():
            output = model(input_tensor)
            probabilities = torch.softmax(output, dim=1)
            confidence, predicted_idx = torch.max(probabilities, 1)
            predicted_label = index_to_label[predicted_idx.item()]
            predictions[name] = {
                'label': predicted_label,
                'confidence': confidence.item() * 100
            }
    return predictions


print(f"\n样本预测结果:")
for sample in test_samples:
    predictions = predict_with_all_models(sample, models, char_to_index, max_len, index_to_label)
    print(f"\n文本: '{sample}'")
    for model_name, pred in predictions.items():
        print(f"  {model_name}: {pred['label']} (置信度: {pred['confidence']:.2f}%)")

# ==================== 模型复杂度对比 ====================
print(f"\n{'=' * 60}")
print("模型复杂度对比")
print(f"{'=' * 60}")


def count_parameters(model):
    """计算模型参数数量"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


print("\n模型参数数量:")
for name in ["RNN", "GRU", "LSTM"]:
    param_count = count_parameters(models[name])
    print(f"  {name}: {param_count:,} 个参数")

print("\n相对复杂度:")
rnn_params = count_parameters(models["RNN"])
gru_params = count_parameters(models["GRU"])
lstm_params = count_parameters(models["LSTM"])

print(f"  GRU参数量是RNN的 {gru_params / rnn_params:.2f} 倍")
print(f"  LSTM参数量是RNN的 {lstm_params / rnn_params:.2f} 倍")
print(f"  LSTM参数量是GRU的 {lstm_params / gru_params:.2f} 倍")

# 保存结果到文件
import json

result_summary = {}
for name in ["RNN", "GRU", "LSTM"]:
    result_summary[name] = {
        'final_train_accuracy': float(results[name]['final_train_accuracy']),
        'final_test_accuracy': float(results[name]['final_test_accuracy']),
        'parameters': int(count_parameters(models[name]))
    }

with open('model_comparison_results.json', 'w', encoding='utf-8') as f:
    json.dump(result_summary, f, indent=2, ensure_ascii=False)

print(f"\n结果已保存到 'model_comparison_results.json'")