from __future__ import annotations

import json
from typing import Any

from engine.config import ActionType, Role


ROLE_DESCRIPTIONS = {
    Role.VILLAGER: "你是普通村民，没有特殊能力。你的目标是找出所有狼人并投票放逐他们。",
    Role.WEREWOLF: "你是狼人。夜晚可以与狼队友一起杀人，白天需要隐藏身份、伪装好人。你的目标是杀光所有村民。",
    Role.SEER: "你是预言家。每晚可以查验一名玩家的阵营——好人（村民阵营）或狼人。法官会以大拇指向上（好）或向下（坏）告知。你需要引导好人阵营获胜。",
    Role.WITCH: "你是女巫。拥有一瓶解药和一瓶毒药。解药可以救活被狼人杀害的玩家，毒药可以在夜晚毒杀任意一名玩家。",
    Role.HUNTER: "你是猎人。当你被放逐或被杀时，可以开枪带走一名玩家。",
    Role.GUARD: "你是守卫。每晚可以守护一名玩家，被守护的玩家当晚不会被狼人杀害。不能连续两晚守护同一人。",
}

ROLE_VICTORY_CONDITIONS = {
    Role.VILLAGER: "好人阵营获胜条件：所有狼人被放逐（屠边规则：狼人杀光所有平民或所有神职即可获胜，好人需保护两类同伴都不能全灭）。",
    Role.WEREWOLF: "狼人阵营获胜条件（屠边）：狼人只需杀光所有平民，或者杀光所有神职（预言家、女巫、猎人、守卫），两者满足其一即可获胜。",
    Role.SEER: "好人阵营获胜条件：所有狼人被放逐（屠边规则：狼人杀光所有平民或所有神职即可获胜，好人需保护两类同伴都不能全灭）。",
    Role.WITCH: "好人阵营获胜条件：所有狼人被放逐（屠边规则：狼人杀光所有平民或所有神职即可获胜，好人需保护两类同伴都不能全灭）。",
    Role.HUNTER: "好人阵营获胜条件：所有狼人被放逐（屠边规则：狼人杀光所有平民或所有神职即可获胜，好人需保护两类同伴都不能全灭）。",
    Role.GUARD: "好人阵营获胜条件：所有狼人被放逐（屠边规则：狼人杀光所有平民或所有神职即可获胜，好人需保护两类同伴都不能全灭）。",
}

ACTION_TYPE_NAMES = {
    ActionType.KILL: "击杀",
    ActionType.INVESTIGATE: "查验",
    ActionType.SAVE: "解救",
    ActionType.POISON: "毒杀",
    ActionType.PROTECT: "守护",
    ActionType.SHOOT: "射击",
    ActionType.VOTE: "投票",
}


class PromptBuilder:
    """构建 LLM 提示词"""

    def build_system_prompt(self, role: Role) -> str:
        return f"""你是狼人杀游戏中的一名玩家。你的角色是：{role.value}。

{ROLE_DESCRIPTIONS.get(role, "")}

{ROLE_VICTORY_CONDITIONS.get(role, "")}

游戏规则：
1. 游戏分为夜晚和白天两个阶段交替进行
2. 夜晚各角色按顺序行动
3. 白天所有存活玩家讨论并投票放逐一名玩家
4. 被放逐的玩家发表遗言后出局
5. 胜利条件为屠边：狼人只需杀光所有平民或所有神职即可获胜，好人需要保护两类同伴都不能全灭

重要规则：
- 不要暴露你的角色信息给其他玩家（除非是合适的时机）
- 狼人可以在白天伪装成好人
- 你的所有发言应该是角色扮演式的，符合你当前的身份
- 基于游戏信息进行逻辑推理
"""

    def _public_state_str(self, observation: dict) -> str:
        lines = [f"第 {observation.get('round', 1)} 回合"]
        lines.append(f"当前阶段: {observation.get('phase', 'unknown')}")
        lines.append(f"存活玩家 ({observation.get('alive_count', 0)}人):")

        for p in observation.get("alive_players", []):
            sheriff = " [警长]" if p.get("is_sheriff") else ""
            lines.append(f"  - 玩家 {p['id']} ({p['name']}){sheriff}")

        if observation.get("eliminated_today") is not None:
            lines.append(f"今日被放逐: 玩家 {observation['eliminated_today']}")

        return "\n".join(lines)

    def _private_state_str(self, role: Role, observation: dict) -> str:
        lines = [f"你的角色: {role.value}", f"你的编号: {observation.get('my_id')}"]

        if role == Role.WEREWOLF:
            mates = observation.get("werewolf_teammates", [])
            if mates:
                lines.append("你的狼队友:")
                for m in mates:
                    lines.append(f"  - 玩家 {m['id']} ({m['name']})")

        if role == Role.SEER:
            seen = observation.get("seen_results", {})
            if seen:
                lines.append("历史查验结果:")
                for pid, r in seen.items():
                    lines.append(f"  玩家 {pid} 是 {r}")

        if role == Role.WITCH:
            lines.append(f"解药已使用: {observation.get('save_potion_used', False)}")
            lines.append(f"毒药已使用: {observation.get('poison_potion_used', False)}")

        return "\n".join(lines)

    def build_night_prompt(
        self,
        role: Role,
        observation: dict,
        night_info: dict,
        available_actions: list[tuple[ActionType, list[int]]],
        memory: str,
    ) -> str:
        prompt = f"""# 游戏状态
{self._public_state_str(observation)}

# 私有信息
{self._private_state_str(role, observation)}

# 夜间信息
{json.dumps(night_info, ensure_ascii=False, indent=2)}

# 历史记忆
{memory}

# 可用行动
"""
        for action_type, targets in available_actions:
            target_str = ", ".join(str(t) for t in targets) if targets else "无可用目标"
            prompt += f"- {ACTION_TYPE_NAMES.get(action_type, action_type.value)}: 可选目标 [{target_str}]\n"

        prompt += f"""\n请根据你的角色和目标做出夜晚行动决策。
对于每个可用行动，选择目标编号。
只需要输出你选择的行动和目标，例如：击杀→3号"""
        return prompt

    def build_discussion_prompt(self, role: Role, observation: dict, memory: str) -> str:
        prompt = f"""# 游戏状态
{self._public_state_str(observation)}

# 私有信息
{self._private_state_str(role, observation)}

# 历史记忆
{memory}

# 讨论阶段
现在进入白天讨论阶段。请简要发言（1-2句话），分析局势或指出可疑玩家。
不要透露你的角色身份（除非有策略需要）。

你的发言："""
        return prompt

    def build_vote_prompt(self, role: Role, observation: dict, memory: str) -> str:
        prompt = f"""# 游戏状态
{self._public_state_str(observation)}

# 私有信息
{self._private_state_str(role, observation)}

# 历史记忆
{memory}

# 投票阶段
现在进入投票阶段。你需要投票放逐一名玩家。
投给谁？请基于讨论情况和你的推理做出决定。

输出格式：vote: 目标编号
如果你不确定可以弃票: vote: -1"""
        return prompt

    def build_hunter_prompt(self, observation: dict) -> str:
        return f"""# 当前局势
{self._public_state_str(observation)}

你是猎人，已被放逐。你可以开枪带走一名玩家。
选择目标：输出 target: 目标编号（-1 表示不开枪）"""
