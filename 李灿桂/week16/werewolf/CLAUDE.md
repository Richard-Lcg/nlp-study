# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

基于多 Agent 协作框架的狼人杀系统。核心在于多智能体的协作/对抗与交互机制设计。

**Python:** Anaconda 3 (`D:\soft\dev\anaconda3`)

## Project Structure

```
werewolf/
├── engine/          # 游戏引擎（无 LLM 依赖）
│   ├── config.py    # GameConfig, Role, GamePhase, ActionType 枚举 + 板子配置
│   ├── game_state.py # GameState, Player, NightAction, GameLog 数据模型
│   ├── rules.py     # Rules: 胜负判定、行动校验、夜晚/白天结算
│   └── engine.py    # GameEngine: 阶段流转、行动收集、信息查询
├── agents/
│   ├── base.py      # Agent 抽象基类 + AgentType 枚举
│   ├── random_agent.py # RandomAgent（测试用基线）
│   ├── llm_agent.py    # LLMAgent（Anthropic SDK 驱动）
│   └── registry.py  # AgentRegistry（创建和管理 Agent）
├── llm/
│   ├── client.py    # LLMClient（Anthropic SDK 封装）
│   └── prompts.py   # PromptBuilder（分角色提示词模板）
├── runner.py        # GameRunner：协调引擎 + Agent，驱动对局循环
├── utils.py         # 日志保存（JSON）、打印工具
└── main.py          # CLI 入口（--players 9|12, --agent random|llm, --seed）
```

## Supported Setups

| 人数 | 配置 |
|------|------|
| 9    | 3狼人 3村民 1预言家 1女巫 1猎人 |
| 12   | 4狼人 4村民 1预言家 1女巫 1猎人 1守卫 |

## Key Design Decisions

- **信息隔离:** Agent 无法直接获取其他玩家的角色信息，通过 `Agent.observe()` 构建信息受限的观测
- **狼人多数决:** 多狼夜晚各自投票，同一目标票数过半才可击杀（平票则平安夜）
- **多死机制:** 女巫毒杀与狼人刀杀是独立事件，当晚可能多人死亡
- **守卫 vs 狼人:** 守护目标与狼人击杀目标相同时，守护生效、击杀被挡

## Running

```bash
# 9 人随机 Agent 对局
python main.py

# 12 人局
python main.py --players 12

# 指定随机种子
python main.py --seed 42

# LLM Agent（需要 ANTHROPIC_API_KEY）
python main.py --agent llm
```

## Advanced Directions

参见 README.md — 三选一：① 通用 Agent 演化 ② 评测复盘+Leaderboard ③ 自进化 Agent
