#!/usr/bin/env python3
"""狼人杀多 Agent 系统 - 入口"""

import argparse
import random

from engine.config import GameConfig, ROLE_SETUPS
from agents import AgentType
from runner import GameRunner
from utils import save_game_log, print_game_log


def main():
    parser = argparse.ArgumentParser(description="狼人杀多 Agent 系统")
    parser.add_argument("--players", type=int, choices=sorted(ROLE_SETUPS.keys()), default=9,
                        help="玩家人数")
    parser.add_argument("--agent", choices=["random", "llm"], default="llm",
                        help="Agent 类型")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子（用于复现）")
    parser.add_argument("--save-log", action="store_true", default=True,
                        help="保存游戏日志到文件")

    args = parser.parse_args()

    config = GameConfig(num_players=args.players)
    agent_type = AgentType.LLM if args.agent == "llm" else AgentType.RANDOM
    seed = args.seed or random.randint(0, 99999)

    runner = GameRunner(config, agent_type=agent_type)
    state = runner.run_game(player_names=[f"玩家{i}" for i in range(config.num_players)])

    if args.save_log and state:
        path = save_game_log(state)
        print(f"\n日志已保存: {path}")


if __name__ == "__main__":
    main()
