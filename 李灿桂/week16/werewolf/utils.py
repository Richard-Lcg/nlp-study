from __future__ import annotations

import json
import os
from datetime import datetime

from engine.config import GamePhase
from engine.game_state import GameState


def save_game_log(state: GameState, log_dir: str = "logs") -> str:
    """将游戏日志保存到文件，返回文件路径"""
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(log_dir, f"game_{timestamp}.json")

    log_data = {
        "winner": state.winner,
        "total_rounds": state.round,
        "players": [
            {
                "id": p.player_id,
                "name": p.name,
                "role": p.role.value,
                "status": p.status.value,
            }
            for p in state.players
        ],
        "logs": [
            {
                "round": log.round,
                "phase": log.phase.value,
                "message": log.message,
                "data": log.data,
            }
            for log in state.logs
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    return filepath


def print_game_log(state: GameState):
    """结构化打印游戏日志"""
    for log in state.logs:
        tag = f"[R{log.round}|{log.phase.value}]"
        print(f"  {tag} {log.message}")
