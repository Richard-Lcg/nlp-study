import torch
import numpy as np
import matplotlib.pyplot as plt

# 1. 生成 sin 函数的数据
# 生成在 [-3π, 3π] 范围内的x值
X_numpy = np.linspace(-3 * np.pi, 3 * np.pi, 200).reshape(-1, 1)
# 生成对应的 sin 函数值，并添加少量噪声
y_numpy = np.sin(X_numpy) + 0.1 * np.random.randn(200, 1)

# 转换为 PyTorch 张量
X = torch.from_numpy(X_numpy).float()
y = torch.from_numpy(y_numpy).float()

print("sin函数数据生成完成。")
print(f"数据形状: X={X.shape}, y={y.shape}")
print("---" * 10)


# 2. 定义一个简单的多层神经网络
# 我们创建一个3层的神经网络：输入层 -> 隐藏层1 -> 隐藏层2 -> 输出层
class SimpleNet(torch.nn.Module):
    def __init__(self):
        super(SimpleNet, self).__init__()
        # 第一层：输入层到隐藏层1 (1个特征 -> 20个神经元)
        self.layer1 = torch.nn.Linear(1, 20)
        # 第二层：隐藏层1到隐藏层2 (20个神经元 -> 10个神经元)
        self.layer2 = torch.nn.Linear(20, 10)
        # 第三层：隐藏层2到输出层 (10个神经元 -> 1个输出)
        self.layer3 = torch.nn.Linear(10, 1)
        # 使用ReLU激活函数，增加非线性
        self.activation = torch.nn.ReLU()

    def forward(self, x):
        # 前向传播过程
        x = self.activation(self.layer1(x))
        x = self.activation(self.layer2(x))
        x = self.layer3(x)  # 输出层不使用激活函数（回归任务）
        return x


# 创建模型实例
model = SimpleNet()
print("神经网络模型结构:")
print(model)
print("---" * 10)

# 3. 定义损失函数和优化器
loss_fn = torch.nn.MSELoss()  # 均方误差损失函数
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)  # Adam优化器

# 4. 训练模型
num_epochs = 2000
loss_history = []  # 记录损失变化

for epoch in range(num_epochs):
    # 前向传播
    y_pred = model(X)

    # 计算损失
    loss = loss_fn(y_pred, y)

    # 反向传播和优化
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    # 记录损失值
    loss_history.append(loss.item())

    # 每200个epoch打印一次损失
    if (epoch + 1) % 200 == 0:
        print(f'Epoch [{epoch + 1}/{num_epochs}], Loss: {loss.item():.6f}')

print("\n训练完成！")
print(f"最终损失: {loss.item():.6f}")
print("---" * 10)

# 5. 使用训练好的模型进行预测
model.eval()  # 设置为评估模式
with torch.no_grad():  # 不需要计算梯度
    # 生成更密集的点用于绘制平滑曲线
    X_plot = torch.linspace(-3 * np.pi, 3 * np.pi, 500).reshape(-1, 1)
    y_plot_pred = model(X_plot)

    # 在训练数据上的预测
    y_pred = model(X)

# 6. 绘制结果
plt.figure(figsize=(14, 5))

# 子图1: 原始数据与模型预测
plt.subplot(1, 2, 1)
plt.scatter(X_numpy, y_numpy, alpha=0.6, s=20, label='原始数据 (带噪声)')
plt.plot(X_plot.numpy(), y_plot_pred.numpy(), 'r-', linewidth=2, label='神经网络拟合')
plt.plot(X_plot.numpy(), np.sin(X_plot.numpy()), 'g--', linewidth=2, label='真实 sin(x)')
plt.xlabel('x')
plt.ylabel('y')
plt.title('多层神经网络拟合 sin 函数')
plt.legend()
plt.grid(True, alpha=0.3)

# 子图2: 训练损失曲线
plt.subplot(1, 2, 2)
plt.plot(loss_history, 'b-', linewidth=1)
plt.xlabel('训练轮次 (Epoch)')
plt.ylabel('损失值 (MSE Loss)')
plt.title('训练损失变化曲线')
plt.yscale('log')  # 使用对数坐标，更容易看清损失下降趋势
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# 7. 评估模型在几个关键点的表现
print("\n模型在关键点的预测效果:")
print("-" * 40)
print(f"{'x值':<10} | {'真实sin(x)':<12} | {'模型预测':<12} | {'误差':<10}")
print("-" * 40)

# 定义几个关键点
key_points = torch.tensor([-2 * np.pi, -np.pi, -np.pi / 2, 0, np.pi / 2, np.pi, 2 * np.pi]).float().reshape(-1, 1)

model.eval()
with torch.no_grad():
    for x in key_points:
        true_y = torch.sin(x).item()
        pred_y = model(x).item()
        error = abs(true_y - pred_y)
        print(f"{x.item():<10.4f} | {true_y:<12.6f} | {pred_y:<12.6f} | {error:<10.6f}")

print("-" * 40)

# 8. 可选：查看模型参数
print("\n模型参数统计:")
for name, param in model.named_parameters():
    if param.requires_grad:
        print(
            f"{name:<15} | 形状: {str(param.shape):<15} | 均值: {param.data.mean():.4f} | 标准差: {param.data.std():.4f}")
