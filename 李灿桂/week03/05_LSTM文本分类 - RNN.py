import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

dataset = pd.read_csv("dataset.csv", sep="\t", header=None)
texts = dataset[0].tolist()
string_labels = dataset[1].tolist()

label_to_index = {label: i for i, label in enumerate(set(string_labels))}
numerical_labels = [label_to_index[label] for label in string_labels]

char_to_index = {'<pad>': 0}
for text in texts:
    for char in text:
        if char not in char_to_index:
            char_to_index[char] = len(char_to_index)

index_to_char = {i: char for char, i in char_to_index.items()}
vocab_size = len(char_to_index)

max_len = 40


class CharRNNDataset(Dataset):
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


class RNNClassifier(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim, num_layers=1):
        super(RNNClassifier, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        # 使用普通RNN替代LSTM
        self.rnn = nn.RNN(
            embedding_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            nonlinearity='tanh'  # 可以是'tanh'或'relu'
        )
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x)
        # RNN返回输出和最后一个隐藏状态
        rnn_out, hidden = self.rnn(embedded)
        # 这是最常用的方法，直接取RNN在最后一个时间步的输出
        last_time_step = rnn_out[:, -1, :]  # (batch_size, hidden_dim)
        out = self.fc(last_time_step)
        return out


# 训练RNN模型
rnn_dataset = CharRNNDataset(texts, numerical_labels, char_to_index, max_len)
rnn_dataloader = DataLoader(rnn_dataset, batch_size=32, shuffle=False)

embedding_dim = 64
hidden_dim = 128
output_dim = len(label_to_index)

rnn_model = RNNClassifier(vocab_size, embedding_dim, hidden_dim, output_dim, num_layers=2)
rnn_criterion = nn.CrossEntropyLoss()
rnn_optimizer = optim.Adam(rnn_model.parameters(), lr=0.001)

num_epochs = 4
for epoch in range(num_epochs):
    rnn_model.train()
    running_loss = 0.0
    for idx, (inputs, labels) in enumerate(rnn_dataloader):
        rnn_optimizer.zero_grad()
        outputs = rnn_model(inputs)
        loss = rnn_criterion(outputs, labels)
        loss.backward()

        # 对RNN特别重要：梯度裁剪防止梯度爆炸
        torch.nn.utils.clip_grad_norm_(rnn_model.parameters(), max_norm=1.0)

        rnn_optimizer.step()
        running_loss += loss.item()
        if idx % 50 == 0:
            print(f"RNN - Batch {idx}, Loss: {loss.item():.4f}")

    print(f"RNN - Epoch [{epoch + 1}/{num_epochs}], Average Loss: {running_loss / len(rnn_dataloader):.4f}")


def classify_text_rnn(text, model, char_to_index, max_len, index_to_label):
    indices = [char_to_index.get(char, 0) for char in text[:max_len]]
    indices += [0] * (max_len - len(indices))
    input_tensor = torch.tensor(indices, dtype=torch.long).unsqueeze(0)

    model.eval()
    with torch.no_grad():
        output = model(input_tensor)

    _, predicted_index = torch.max(output, 1)
    predicted_index = predicted_index.item()
    predicted_label = index_to_label[predicted_index]

    return predicted_label


index_to_label = {i: label for label, i in label_to_index.items()}

new_text = "帮我导航到北京"
predicted_class = classify_text_rnn(new_text, rnn_model, char_to_index, max_len, index_to_label)
print(f"RNN预测 - 输入 '{new_text}' 预测为: '{predicted_class}'")

new_text_2 = "查询明天北京的天气"
predicted_class_2 = classify_text_rnn(new_text_2, rnn_model, char_to_index, max_len, index_to_label)
print(f"RNN预测 - 输入 '{new_text_2}' 预测为: '{predicted_class_2}'")