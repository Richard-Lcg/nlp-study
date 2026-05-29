# 狼人杀多 Agent 系统

基于多 Agent 协作框架的狼人杀（Werewolf）信息不对称博弈系统。每个 Agent 根据角色拥有独立目标、策略与行动空间，在严格信息隔离下进行推理、发言与决策。

---

## 项目结构

```
werewolf/
├── api/                     # FastAPI RESTful API
│   ├── server.py            # 观战台后端（FastAPI + uvicorn，端口 8080）
│   └── game_session.py      # 游戏会话管理（单步执行支持）
│
├── engine/                  # 游戏引擎（无 LLM 依赖）
│   ├── config.py            # GameConfig / Role / GamePhase / ActionType
│   ├── game_state.py        # GameState / Player / NightAction / GameLog
│   ├── rules.py             # Rules: 胜负判定、行动校验、夜晚/白天结算
│   └── engine.py            # GameEngine: 阶段流转、行动收集、信息查询
│
├── agents/                  # Agent 框架
│   ├── base.py              # Agent 抽象基类（observe 信息隔离接口）
│   ├── random_agent.py      # RandomAgent（测试用基线）
│   ├── llm_agent.py         # LLMAgent（LLM 驱动，支持 Anthropic 等 API）
│   └── registry.py          # AgentRegistry（创建与管理 Agent）
│
├── llm/                     # LLM 集成
│   ├── client.py            # LLMClient（从 config/config.yaml 读取配置）
│   └── prompts.py           # PromptBuilder（分角色提示词模板）
│
├── config/
│   └── config.yaml          # LLM 配置（api_key / model / base_url）
│
├── frontend/                # 观战台前端（Vite 开发服务器）
│   ├── index.html           # 观战台 SPA
│   ├── style.css            # 深色主题样式
│   ├── app.js               # 前端交互逻辑
│   ├── vite.config.js       # Vite 配置（代理 /api → :8080）
│   └── package.json         # 前端依赖
│
├── test/                    # 117 个单元测试
│   ├── test_config.py
│   ├── test_config_loading.py
│   ├── test_game_state.py
│   ├── test_rules.py
│   ├── test_engine.py
│   ├── test_agents.py
│   └── test_runner.py
│
├── runner.py                # GameRunner：协调引擎 + Agent 驱动对局
├── utils.py                 # 日志保存 / 打印工具
├── main.py                  # CLI 入口
├── logs/                    # 游戏日志输出目录
├── CLAUDE.md
└── README.md
```

---

## 快速开始

```bash
# 1️⃣ 安装后端依赖
pip install fastapi uvicorn anthropic pyyaml

# 2️⃣ 安装前端依赖
cd frontend && npm install && cd ..

# 3️⃣ 启动后端服务（端口 8080，热重载）
uvicorn api.server:app --reload --host 0.0.0.0 --port 8080

# 4️⃣ 新开终端，启动前端开发服务器（端口 5173）
cd frontend && npm run dev

# 5️⃣ 浏览器打开
#    http://localhost:5173

# 6️⃣ 在观战台中选择 LLM Agent，点击「开始游戏」即可实时对局
#    也可选「单步执行」逐步观战，或「运行到底」直接看结局
```

---

## 角色说明

| 角色 | 阵营 | 能力 | 9人局 | 12人局 |
|------|------|------|-------|--------|
| 🐺 狼人 Werewolf | 狼人 | 夜晚与队友协商击杀一人 | 3 | 4 |
| 👤 村民 Villager | 好人 | 白天投票放逐狼人 | 3 | 4 |
| 🔮 预言家 Seer | 好人 | 每晚查验一人的真实身份 | 1 | 1 |
| 🧪 女巫 Witch | 好人 | 解药救被杀者 + 毒药毒杀一人 | 1 | 1 |
| 🏹 猎人 Hunter | 好人 | 被放逐/被杀时开枪带走一人 | 1 | 1 |
| 🛡️ 守卫 Guard | 好人 | 每晚守护一人免被狼杀 | — | 1 |

---

## 游戏阶段说明

### 夜晚阶段（夜间按顺序执行）

| 阶段 | 行动者 | 动作 | 说明 |
|------|--------|------|------|
| 🌙 守卫行动 | 守卫 | 选择守护目标 | 不能连续两晚守护同一人 |
| 🌙 狼人行动 | 全体狼人 | 协商击杀一人 | 多数决：票数过半才击杀，平票则平安夜 |
| 🌙 预言家行动 | 预言家 | 查验一名玩家身份 | 得知该玩家确切阵营/角色 |
| 🌙 女巫行动 | 女巫 | 救人或毒人 | 可救被杀者（解药未用），也可毒杀任意一人（毒药未用） |

### 白天阶段

| 阶段 | 参与方 | 动作 | 说明 |
|------|--------|------|------|
| ☀️ 讨论 | 全体存活 | 依次发言 | 自由讨论分析局势 |
| 🗳️ 投票 | 全体存活 | 投票放逐 | 平票或无人投票则无放逐 |
| 💬 遗言 | 被放逐者 | 遗言 | 猎人被放逐可开枪带走一人 |

### 特殊结算规则

| 规则 | 说明 |
|------|------|
| 🛡️ 守卫挡刀 | 守护目标 = 狼人击杀目标时，守护生效、击杀无效 |
| ☠️ 双死机制 | 狼人刀杀 + 女巫毒杀不同目标时，当夜两人同时死亡 |
| 🔫 猎人开枪 | 猎人被放逐或夜晚被杀时，可开枪带走任意存活一人 |
| 🏆 好人胜 | 所有狼人死亡 |
| 🏆 狼人胜 | 存活狼人数 ≥ 存活好人数 |

---

## REST API

| 方法 | 路径 | 功能 |
|------|------|------|
| `POST` | `/api/session/create` | 创建新游戏会话（实时对局） |
| `GET` | `/api/session/{id}` | 获取会话当前状态 |
| `POST` | `/api/session/{id}/step` | 单步执行 |
| `POST` | `/api/session/{id}/run` | 运行至结束 |
| `GET` | `/api/games` | 获取所有历史对局列表 |
| `GET` | `/api/games/{filename}` | 获取指定对局的完整 JSON 日志 |

**基地址**: `http://localhost:8080` （后端端口）

**示例**：

```bash
# 列出所有历史对局
curl http://localhost:8080/api/games

# 获取特定对局详情
curl http://localhost:8080/api/games/game_20260528_162656.json

# 创建实时对局会话（9人 LLM Agent）
curl -X POST "http://localhost:8080/api/session/create?num_players=9&agent_type=llm"

# 单步执行
curl -X POST "http://localhost:8080/api/session/{session_id}/step"
```

**返回结构** (`/api/games`):

```json
[
  {
    "filename": "game_20260528_162656.json",
    "time": "20260528_162656",
    "winner": "werewolf",
    "total_rounds": 1,
    "players": [
      {"id": 0, "name": "玩家0", "role": "werewolf", "status": "alive"}
    ],
    "log_count": 308
  }
]
```

**返回结构** (`/api/games/{filename}`):

```json
{
  "winner": "werewolf",
  "total_rounds": 5,
  "players": [...],
  "logs": [
    {"round": 1, "phase": "night_werewolf", "message": "游戏开始", "data": {}}
  ]
}
```

---

## CLI 参数

```bash
python main.py --help
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--players` | `9` | 玩家人数（9 或 12） |
| `--agent` | `llm` | Agent 类型（`random` / `llm`） |
| `--seed` | 随机 | 随机种子，指定后对局可复现 |
| `--save-log` | `true` | 保存日志到 `logs/` 目录 |

---

## 核心接口

### GameConfig

```python
from engine.config import GameConfig

# 9人标准局
config = GameConfig(num_players=9)
# 12人局
config = GameConfig(num_players=12)
# 自定义配置
config = GameConfig(num_players=9, discussion_timeout=120, vote_timeout=60)
```

### GameEngine

```python
from engine.config import GameConfig, Role, ActionType
from engine.engine import GameEngine

engine = GameEngine(GameConfig(num_players=9))
state = engine.init_game([f"P{i}" for i in range(9)], random_seed=42)

# 获取可用行动
actions = engine.get_available_actions(player_id)

# 提交行动
engine.submit_night_action(actor_id, ActionType.KILL, target_id)

# 提交投票
engine.submit_vote(voter_id, target_id)

# 结算
deaths = engine.resolve_night()
eliminated = engine.resolve_day()

# 检查胜负
winner = engine.check_game_over()
```

### GameRunner

```python
from engine.config import GameConfig
from agents import AgentType
from runner import GameRunner

runner = GameRunner(
    config=GameConfig(num_players=9),
    agent_type=AgentType.RANDOM,  # 或 AgentType.LLM
)
state = runner.run_game()

print(f"胜方: {state.winner}")      # "werewolf" / "village"
print(f"总轮数: {state.round}")
print(f"日志条数: {len(state.logs)}")
```

### 自定义 Agent

```python
from agents.base import Agent
from engine.config import ActionType

class MyAgent(Agent):
    def on_night(self, state, available_actions, night_info):
        return [(ActionType.KILL, target_id)]

    def on_discussion(self, state):
        return "我认为 X 号是狼人。"

    def on_vote(self, state):
        return target_id  # -1 弃票

    def on_hunter_shot(self, state):
        return target_id  # None 不开枪

    def on_last_words(self, state):
        return "我是好人。"
```

---

## 测试

```bash
# 全部 117 个测试
python -m pytest test/ -v

# 指定模块
python -m pytest test/test_rules.py -v
python -m pytest test/test_engine.py -v
python -m pytest test/test_runner.py -v

# 多局双方胜率验证
python -m pytest test/test_runner.py::TestGameRunner::test_multiple_games_both_sides_can_win -v
```

---

## 进阶方向

1. **通用 Agent → 狼人杀角色 Agent 演化** — 探索"读懂自己→修改自己→运行自己"的自演化系统
2. **评测 + 复盘** — 构建多维可量化评测体系，产出不同版本/模型 Agent 同台竞技的 Leaderboard
3. **自进化 Agent** — 实现"对局→分析→优化→再对局"的自进化循环
