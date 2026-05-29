/* 狼人杀观战台 - 前端逻辑 */

// ========== 实时对局状态 ==========
let sessionId = null;
let sessionLogs = [];
let isGameOver = false;
let isRunning = false;

// ========== 历史回放状态 ==========
let gameData = null;
let logs = [];
let currentIndex = -1;
let replayTimer = null;
let isReplaying = false;
const REPLAY_INTERVAL = 1200;

// ========== 初始化 ==========
document.addEventListener("DOMContentLoaded", () => {
  fetchGameList();
});

// ========== Tab 切换 ==========
function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
  document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add("active");
  document.getElementById(`tab-${tab}`).classList.add("active");
}

// =====================================================
//  实时对局（Live Game）
// =====================================================

function startGame() {
  const numPlayers = parseInt(document.getElementById("live-players").value);

  setLiveStatus("正在创建游戏...");
  setButtonsDisabled(true, true, true);

  fetch("/api/session/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ num_players: numPlayers }),
  })
    .then(r => r.json())
    .then(res => {
      if (!res.success) throw new Error(res.error || "创建失败");
      sessionId = res.session.session_id;
      isGameOver = res.session.game_over;
      sessionLogs = res.session.logs || [];
      renderLiveState(res.session);
      setButtonsDisabled(false, false, true); // step, run 可用
      setLiveStatus(`对局中 | ${res.session.log_count} 条日志`);
    })
    .catch(err => {
      setLiveStatus("创建失败: " + err.message);
      console.error(err);
      setButtonsDisabled(false, true, true);
    });
}

function stepGame() {
  if (!sessionId) return;

  setButtonsDisabled(true, true, true);
  setLiveStatus("执行中...");

  fetch(`/api/session/${sessionId}/step`, { method: "POST" })
    .then(r => r.json())
    .then(res => {
      if (!res.success) throw new Error(res.error || "执行失败");
      isGameOver = res.session.game_over;
      sessionLogs = res.session.logs || [];
      renderLiveState(res.session);

      if (isGameOver) {
        setButtonsDisabled(true, true, true);
        const wMap = { werewolf: "狼人", village: "好人" };
        setLiveStatus(`游戏结束！${wMap[res.session.winner] || "?"} 胜 | 共 ${res.session.log_count} 条日志`);
      } else {
        setButtonsDisabled(false, false, false);
        setLiveStatus(`对局中 | ${res.session.log_count} 条日志`);
      }
    })
    .catch(err => {
      setLiveStatus("执行失败: " + err.message);
      console.error(err);
      setButtonsDisabled(false, false, false);
    });
}

function runToEnd() {
  if (!sessionId || isRunning) return;

  isRunning = true;
  setButtonsDisabled(true, true, true);
  setLiveStatus("运行中...");

  fetch(`/api/session/${sessionId}/run`, { method: "POST" })
    .then(r => r.json())
    .then(res => {
      if (!res.success) throw new Error(res.error || "运行失败");
      isGameOver = true;
      sessionLogs = res.session.logs || [];
      renderLiveState(res.session);
      setButtonsDisabled(true, true, true);
      const wMap = { werewolf: "狼人", village: "好人" };
      setLiveStatus(`游戏结束！${wMap[res.session.winner] || "?"} 胜 | 共 ${res.session.log_count} 条日志`);
    })
    .catch(err => {
      setLiveStatus("运行失败: " + err.message);
      console.error(err);
    })
    .finally(() => {
      isRunning = false;
    });
}

function renderLiveState(snapshot) {
  // 玩家列表
  renderLivePlayers(snapshot);

  // 阶段 banner
  const phaseBanner = document.getElementById("live-phase-banner");
  const lastLog = sessionLogs.length > 0 ? sessionLogs[sessionLogs.length - 1] : null;
  if (snapshot.game_over) {
    const winner = snapshot.winner === "werewolf" ? "🐺 狼人" : "👤 好人";
    phaseBanner.textContent = `🏁 游戏结束 — ${winner} 获胜！`;
    phaseBanner.className = "game_over";
  } else if (lastLog) {
    const phase = lastLog.phase;
    const labels = {
      night_guard: "🌙 守卫行动", night_werewolf: "🌙 狼人行动",
      night_seer: "🌙 预言家查验", night_witch: "🌙 女巫行动",
      day_discussion: "☀️ 白天讨论", day_vote: "🗳️ 投票放逐",
      game_over: "🏁 游戏结束",
    };
    phaseBanner.textContent = labels[phase] || phase;
    if (["night_guard","night_werewolf","night_seer","night_witch"].includes(phase)) {
      phaseBanner.className = "night";
    } else if (phase === "day_discussion") {
      phaseBanner.className = "day";
    } else if (phase === "day_vote") {
      phaseBanner.className = "vote";
    } else {
      phaseBanner.className = "";
    }
  } else {
    phaseBanner.textContent = "等待开始游戏...";
    phaseBanner.className = "";
  }

  // 回合信息
  document.getElementById("live-round-info").textContent =
    `第 ${snapshot.round_count || snapshot.round || 0} 回合`;

  // 主舞台最新日志
  const stage = document.getElementById("live-stage-content");
  if (lastLog) {
    const phase = lastLog.phase;

    // 白天讨论时列出当前回合所有玩家的发言
    if (phase === "day_discussion") {
      const round = lastLog.round;
      const discussions = sessionLogs.filter(
        l => l.phase === "day_discussion" && l.round === round && l.message.includes(":")
      );
      if (discussions.length > 1) {
        stage.textContent = discussions.map(d => d.message).join("\n");
      } else {
        stage.textContent = lastLog.message;
      }
    } else if (phase === "day_vote") {
      // 投票阶段显示全部投票信息
      const round = lastLog.round;
      const voteMsgs = sessionLogs.filter(
        l => l.phase === "day_vote" && l.round === round
      );
      stage.textContent = voteMsgs.map(m => m.message).join("\n");
    } else {
      stage.textContent = lastLog.message;
    }
  } else {
    stage.textContent = "点击「开始游戏」创建对局";
  }

  // 日志列表
  renderLiveLogs(sessionLogs);
}

function renderLivePlayers(snapshot) {
  const container = document.getElementById("live-player-list");
  container.innerHTML = "";

  const allPlayers = snapshot.alive_players || [];
  const deadPlayers = snapshot.dead_players || [];

  allPlayers.forEach(p => {
    container.appendChild(createPlayerCard(p, false));
  });
  deadPlayers.forEach(p => {
    container.appendChild(createPlayerCard(p, true));
  });
}

function createPlayerCard(player, isDead) {
  const labels = {
    werewolf: "🐺 狼人", villager: "👤 村民", seer: "🔮 预言家",
    witch: "🧪 女巫", hunter: "🏹 猎人", guard: "🛡️ 守卫",
    unknown: "❓ 未知",
  };

  const card = document.createElement("div");
  card.className = "player-card" + (isDead ? " dead" : "");
  card.innerHTML = `
    <span class="id">#${player.id}</span>
    <span>${player.name}</span>
    <span class="role-badge ${player.role}">${labels[player.role] || player.role}</span>
  `;
  return card;
}

function renderLiveLogs(logs) {
  const container = document.getElementById("live-log-container");

  // 判断是否应该自动滚动到底部（用户已在底部 或 首次渲染）
  const shouldScroll = container.scrollHeight === 0 ||
    container.scrollTop >= container.scrollHeight - container.clientHeight - 50;

  container.innerHTML = "";

  logs.forEach((entry, i) => {
    const div = document.createElement("div");
    div.className = `log-entry ${getLogClass(entry)}`;
    div.dataset.index = i;

    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = `[${PHASE_CN_NAMES[entry.phase] || entry.phase}]`;
    div.appendChild(tag);

    const text = document.createElement("span");
    const truncated = entry.message.length > 60;
    text.textContent = truncated
      ? entry.message.substring(0, 57) + "..."
      : entry.message;
    if (truncated) text.title = entry.message;
    div.appendChild(text);

    container.appendChild(div);
  });

  // 仅在用户已在底部或首次渲染时滚动到底部
  if (shouldScroll) {
    container.scrollTop = container.scrollHeight;
  }
}

function getLogClass(entry) {
  const msg = entry.message;
  if (msg.includes("===")) return "phase-marker";
  if (msg.includes(":") && entry.phase === "day_discussion") return "speech";
  if (["night_guard", "night_werewolf", "night_seer", "night_witch"].includes(entry.phase)) return "action";
  if (msg.includes("死了") || msg.includes("被放逐")) return "death";
  if (msg.includes("投票给")) return "vote";
  if (msg.includes("游戏结束") || msg.includes("获胜")) return "result";
  return "";
}

function setButtonsDisabled(start, step, run) {
  document.getElementById("btn-start").disabled = start;
  document.getElementById("btn-step").disabled = step;
  document.getElementById("btn-run").disabled = run;
}

function setLiveStatus(text) {
  document.getElementById("status").textContent = text;
}


// =====================================================
//  历史对局（History Replay）
// =====================================================

function fetchGameList() {
  fetch("/api/games")
    .then(r => r.json())
    .then(games => {
      const sel = document.getElementById("game-select");
      sel.innerHTML = '<option value="">-- 选择对局 --</option>';
      games.forEach(g => {
        const opt = document.createElement("option");
        opt.value = g.filename;
        const time = formatTime(g.time);
        const wLabel = g.winner === "werewolf" ? "狼人" : g.winner === "village" ? "好人" : "?";
        opt.textContent = `${time} | ${wLabel}胜 | ${g.total_rounds}轮 | ${g.players.length}人`;
        sel.appendChild(opt);
      });
      if (games.length > 0) {
        sel.value = games[0].filename;
        loadGame(games[0].filename);
      }
      if (!sessionId) {
        document.getElementById("status").textContent = `共 ${games.length} 局`;
      }
    })
    .catch(err => {
      if (!sessionId) document.getElementById("status").textContent = "获取列表失败";
      console.error(err);
    });
}

function loadGame(filename) {
  if (!filename) return;
  stopReplay();
  document.getElementById("status").textContent = "加载中...";

  fetch(`/api/games/${filename}`)
    .then(r => r.json())
    .then(data => {
      gameData = data;
      logs = data.logs || [];
      currentIndex = -1;
      renderInitialState();
      renderPlayerList(data.players, data.winner);
      renderLogList();
      enableSlider();
      document.getElementById("status").textContent = `${logs.length} 条日志`;
    })
    .catch(err => {
      document.getElementById("status").textContent = "加载失败";
      console.error(err);
    });
}

function renderInitialState() {
  setPhase("等待开始", "");
  document.getElementById("round-info").textContent = "";
  document.getElementById("stage-content").textContent =
    "选择左侧日志条目开始观战，或点击「自动回放」从头观看。";
  document.getElementById("progress-text").textContent = `0 / ${logs.length}`;
}

function enableSlider() {
  const slider = document.getElementById("log-slider");
  slider.max = Math.max(0, logs.length - 1);
  slider.value = -1;
}

const ROLE_LABELS = {
  werewolf: "🐺 狼人", villager: "👤 村民", seer: "🔮 预言家",
  witch: "🧪 女巫", hunter: "🏹 猎人", guard: "🛡️ 守卫",
};

const PHASE_CN_NAMES = {
  night_guard: "守卫夜晚", night_werewolf: "狼人夜晚", night_seer: "预言家夜晚",
  night_witch: "女巫夜晚", day_discussion: "白天讨论", day_vote: "投票放逐",
  day_last_words: "遗言", game_over: "游戏结束",
};

function renderPlayerList(players, winner) {
  const container = document.getElementById("player-list");
  container.innerHTML = "";
  players.forEach(p => {
    const card = document.createElement("div");
    card.className = "player-card" + (p.status === "dead" || p.status === "dying" ? " dead" : "");
    card.id = `player-${p.id}`;
    card.innerHTML = `
      <span class="id">#${p.id}</span>
      <span>${p.name}</span>
      <span class="role-badge ${p.role}">${ROLE_LABELS[p.role] || p.role}</span>
    `;
    container.appendChild(card);
  });
}

function highlightPlayer(playerId, className) {
  const el = document.getElementById(`player-${playerId}`);
  if (el) {
    el.classList.remove("killed", "voted", "highlight");
    if (className) el.classList.add(className);
  }
}

function clearHighlights() {
  document.querySelectorAll("#player-list .player-card").forEach(c => {
    c.classList.remove("killed", "voted", "highlight");
  });
}

function setPhase(text, cls) {
  const banner = document.getElementById("phase-banner");
  banner.textContent = text;
  banner.className = cls;
}

function stepLog(direction) {
  const newIdx = Math.max(-1, Math.min(logs.length - 1, currentIndex + direction));
  jumpTo(newIdx);
}

function jumpTo(index) {
  if (index < -1 || index >= logs.length) return;
  currentIndex = index;
  document.getElementById("log-slider").value = Math.max(0, index);
  document.getElementById("progress-text").textContent =
    `${index + 1} / ${logs.length}`;

  if (index === -1) {
    renderInitialState();
    clearHighlights();
    document.querySelectorAll("#log-container .log-entry").forEach(e => e.classList.remove("active"));
    return;
  }

  document.querySelectorAll("#log-container .log-entry").forEach(e => e.classList.remove("active"));
  const entryEl = document.querySelector(`#log-container .log-entry[data-index="${index}"]`);
  if (entryEl) {
    entryEl.classList.add("active");
    entryEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  renderStateUpTo(index);
}

function renderStateUpTo(index) {
  const relevant = logs.slice(0, index + 1);
  const lastEntry = logs[index];
  const stage = document.getElementById("stage-content");

  const phase = lastEntry.phase;
  drawPhaseBanner(phase, lastEntry);
  drawRoundInfo(lastEntry);

  updatePlayerStatus(relevant);

  clearHighlights();

  if (lastEntry.message.includes("死了") || lastEntry.message.includes("被放逐")) {
    const match = lastEntry.message.match(/玩家 (\d+)/);
    if (match) highlightPlayer(parseInt(match[1]), "killed");
  }
  if (lastEntry.message.includes("投票给")) {
    const match = lastEntry.message.match(/玩家 (\d+)\[.*?\] 投票给玩家 (\d+)/);
    if (match) {
      highlightPlayer(parseInt(match[2]), "voted");
    }
  }
  if (["投票杀死", "查验身份", "用解药救活", "用毒药毒杀", "守护"].some(act => lastEntry.message.includes(act))) {
    const match = lastEntry.message.match(/玩家 (\d+)\[/);
    if (match) highlightPlayer(parseInt(match[1]), "highlight");
  }

  // 白天讨论时列出所有玩家的发言
  if (phase === "day_discussion") {
    const round = lastEntry.round;
    const discussions = logs.filter(
      l => l.phase === "day_discussion" && l.round === round && l.message.includes(":")
    );
    if (discussions.length > 0) {
      stage.textContent = discussions.map(d => d.message).join("\n");
    } else {
      stage.textContent = formatLogMessage(lastEntry, true);
    }
  } else if (phase === "day_vote") {
    // 投票阶段显示全部投票信息
    const round = lastEntry.round;
    const voteMsgs = logs.filter(
      l => l.phase === "day_vote" && l.round === round
    );
    stage.textContent = voteMsgs.map(m => m.message).join("\n");
  } else {
    stage.textContent = formatLogMessage(lastEntry, true);
  }
}

function drawPhaseBanner(phase, entry) {
  const labels = {
    night_guard: "🌙 守卫行动", night_werewolf: "🌙 狼人行动",
    night_seer: "🌙 预言家查验", night_witch: "🌙 女巫行动",
    day_discussion: "☀️ 白天讨论", day_vote: "🗳️ 投票放逐",
    day_last_words: "💬 遗言", game_over: "🏁 游戏结束",
  };
  const classes = {
    night_guard: "night", night_werewolf: "night", night_seer: "night", night_witch: "night",
    day_discussion: "day", day_vote: "vote", game_over: "game_over",
  };
  setPhase(labels[phase] || phase, classes[phase] || "");
}

function drawRoundInfo(entry) {
  document.getElementById("round-info").textContent =
    `第 ${entry.round || "?"} 回合`;
}

function updatePlayerStatus(relevantLogs) {
  if (!gameData) return;
  gameData.players.forEach(p => {
    const card = document.getElementById(`player-${p.id}`);
    if (!card) return;

    relevantLogs.forEach(log => {
      const deathMatch = log.message.match(/玩家 (\d+)\[.*?\]）死了/);
      const voteMatch = log.message.match(/玩家 (\d+)（.*?）\[.*?\] 被放逐/);
      const pid = deathMatch ? parseInt(deathMatch[1]) : (voteMatch ? parseInt(voteMatch[1]) : -1);
      if (pid === p.id) {
        card.classList.add("dead");
      }
    });
  });
}

function renderLogList() {
  const container = document.getElementById("log-container");
  container.innerHTML = "";

  logs.forEach((entry, i) => {
    const div = document.createElement("div");
    div.className = `log-entry ${getLogClass(entry)}`;
    div.dataset.index = i;
    div.onclick = () => jumpTo(i);

    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = `[${PHASE_CN_NAMES[entry.phase] || entry.phase}]`;
    div.appendChild(tag);

    const text = document.createElement("span");
    const truncated = entry.message.length > 60;
    text.textContent = truncated
      ? entry.message.substring(0, 57) + "..."
      : entry.message;
    if (truncated) text.title = entry.message;
    div.appendChild(text);

    container.appendChild(div);
  });
}

function formatLogMessage(entry, detailed) {
  let msg = entry.message;
  if (!detailed) {
    if (msg.length > 60) return msg.substring(0, 57) + "...";
  }
  return msg;
}

function toggleReplay() {
  if (isReplaying) {
    stopReplay();
  } else {
    startReplay();
  }
}

function startReplay() {
  if (!gameData) return;
  if (currentIndex >= logs.length - 1) {
    currentIndex = -1;
  }
  isReplaying = true;
  document.getElementById("btn-replay").textContent = "⏸ 暂停";
  doReplayStep();
}

function stopReplay() {
  isReplaying = false;
  document.getElementById("btn-replay").textContent = "▶ 自动回放";
  if (replayTimer) {
    clearTimeout(replayTimer);
    replayTimer = null;
  }
}

function doReplayStep() {
  if (!isReplaying) return;
  if (currentIndex >= logs.length - 1) {
    stopReplay();
    document.getElementById("status").textContent = "回放完成";
    return;
  }
  stepLog(1);
  replayTimer = setTimeout(doReplayStep, REPLAY_INTERVAL);
}

function formatTime(t) {
  if (!t || t.length < 4) return t;
  const y = t.substring(0, 4);
  const m = t.substring(4, 6);
  const d = t.substring(6, 8);
  const h = t.substring(9, 11);
  const mi = t.substring(11, 13);
  return `${y}-${m}-${d} ${h}:${mi}`;
}
