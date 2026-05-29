"""狼人杀观战台 API — FastAPI 服务（端口 8080）"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from agents import AgentType
from api.game_session import GameSessionManager

app = FastAPI(title="狼人杀观战台 API", version="1.0.0")

# ---- CORS（允许前端 5173 跨域） ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
FRONTEND_DIR = BASE_DIR / "frontend"

# 游戏会话管理器
session_manager = GameSessionManager()


# ---- 游戏会话 API ----

@app.post("/api/session/create")
def create_session(body: dict | None = None):
    """创建新游戏会话（使用 LLM Agent）"""
    data = body or {}
    num_players = data.get("num_players", 9)
    t0 = time.time()
    names = [f"玩家{i}" for i in range(num_players)]
    snapshot = session_manager.create_session(
        num_players=num_players,
        agent_type=AgentType.LLM,
        player_names=names,
    )
    sid = snapshot.get("session_id", "?")
    print(f"[API] POST /api/session/create -> {sid} ({num_players}人) [{time.time()-t0:.1f}s]")
    return {"success": True, "session": snapshot}


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """获取会话当前状态"""
    t0 = time.time()
    snapshot = session_manager.get_session_state(session_id)
    if snapshot is None:
        raise HTTPException(404, "Session not found")
    print(f"[API] GET /api/session/{session_id[:8]}... [{time.time()-t0:.1f}s]")
    return {"success": True, "session": snapshot}


@app.post("/api/session/{session_id}/step")
def step_session(session_id: str):
    """单步执行"""
    t0 = time.time()
    print(f"[API] POST /api/session/{session_id[:8]}.../step -> 开始")
    snapshot = session_manager.step_session(session_id)
    if snapshot is None:
        raise HTTPException(404, "Session not found")
    print(f"[API] POST /api/session/{session_id[:8]}.../step -> done [{time.time()-t0:.1f}s]")
    return {"success": True, "session": snapshot}


@app.post("/api/session/{session_id}/run")
def run_session(session_id: str):
    """运行至结束"""
    t0 = time.time()
    print(f"[API] POST /api/session/{session_id[:8]}.../run -> 开始（连续运行）")
    snapshot = session_manager.run_session_to_end(session_id)
    if snapshot is None:
        raise HTTPException(404, "Session not found")
    print(f"[API] POST /api/session/{session_id[:8]}.../run -> 结束 [{time.time()-t0:.1f}s]")
    return {"success": True, "session": snapshot}


# ---- 历史对局 API ----

@app.get("/api/games")
def list_games():
    """获取所有历史对局列表"""
    LOG_DIR.mkdir(exist_ok=True)
    games = []
    for f in sorted(LOG_DIR.glob("game_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            games.append({
                "filename": f.name,
                "time": f.stem.replace("game_", ""),
                "winner": data.get("winner"),
                "total_rounds": data.get("total_rounds"),
                "players": [
                    {"id": p["id"], "name": p["name"], "role": p["role"], "status": p["status"]}
                    for p in data.get("players", [])
                ],
                "log_count": len(data.get("logs", [])),
            })
        except Exception:
            continue
    return games


@app.get("/api/games/{filename}")
def get_game_log(filename: str):
    """获取指定对局的完整日志"""
    if not filename.endswith(".json"):
        raise HTTPException(400, "Invalid file format")

    filepath = LOG_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Game log not found")

    data = json.loads(filepath.read_text(encoding="utf-8"))
    return data


# ---- 前端静态文件 ----

@app.get("/")
def index():
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/{filename:path}")
def static_files(filename: str):
    filepath = FRONTEND_DIR / filename
    if filepath.is_file():
        return FileResponse(filepath)
    raise HTTPException(404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
