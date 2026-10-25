"""
斗地主游戏调度管理器
- 融入真实角色敌友判定与精准战术提示
- 支持 429 限频 5 次自动重试与 60 秒充裕思考上限
- 支持每位玩家席位独立台面出牌展示 (一轮结束后自动清空)
- 纯代码确定性规则裁判公证
"""
import random
import copy
import json
import os
import time
from doudizhu_rules import create_deck, sort_cards, parse_card_pattern, CardType, find_valid_move, get_legal_candidates, format_move_label, get_card_rank
from ai_players import FREE_MODEL_ROSTER, stream_model_api, parse_natural_play, check_cards_validity

RECORD_PATH = os.path.join(os.path.dirname(__file__), 'latest_game_record.json')

class GameManager:
    def __init__(self):
        self.selected_models = [
            "GLM-4-Flash",
            "GLM-Z1-Flash",
            "Qwen/Qwen2.5-7B-Instruct"
        ]
        self.state = {
            "game_id": 0,
            "status": "idle",
            "landlord_idx": 0,
            "bottom_cards": [],
            "current_turn": 0,
            "last_turn_idx": -1,
            "last_action_type": "",
            "last_valid_play": [],
            "last_valid_player_name": "",
            "pass_count": 0,
            "trick_played": {"0": None, "1": None, "2": None},
            "winner": None,
            "winner_role": None,
            "players": [],
            "turns_record": [],
            "system_logs": []
        }
        self.reset_game()

    def set_lineup(self, model_names):
        if len(model_names) == 3:
            self.selected_models = model_names
        return self.reset_game()

    def reset_game(self):
        deck = create_deck()
        random.shuffle(deck)

        landlord_idx = random.randint(0, 2)
        bottom_cards = deck[51:54]

        seats = ["底部 (主视角)", "右方 (下家)", "左方 (上家)"]

        players = []
        for i in range(3):
            model_key = self.selected_models[i] if i < len(self.selected_models) else "GLM-4-Flash"
            base_info = copy.deepcopy(FREE_MODEL_ROSTER.get(model_key, FREE_MODEL_ROSTER["GLM-4-Flash"]))
            hand = deck[i*17 : (i+1)*17]
            role = "地主" if i == landlord_idx else "农民"
            if i == landlord_idx:
                hand.extend(bottom_cards)

            base_info["seat_idx"] = i
            base_info["seat"] = seats[i]
            base_info["role"] = role
            base_info["hand"] = sort_cards(hand)
            base_info["last_action"] = ""
            base_info["last_thinking"] = "入场就绪，等待出牌..."
            base_info["is_legal_last"] = True
            base_info["illegal_reason_last"] = ""
            players.append(base_info)

        landlord_name = players[landlord_idx]["name"]

        self.state = {
            "game_id": self.state.get("game_id", 0) + 1,
            "status": "playing",
            "landlord_idx": landlord_idx,
            "bottom_cards": bottom_cards,
            "current_turn": landlord_idx,
            "last_turn_idx": -1,
            "last_action_type": "",
            "last_valid_play": [],
            "last_valid_player_name": "",
            "pass_count": 0,
            "trick_played": {"0": None, "1": None, "2": None},
            "winner": None,
            "winner_role": None,
            "players": players,
            "turns_record": [],
            "system_logs": [{
                "time": "开局",
                "tag": "发牌公证",
                "text": f"系统自动完成 54 张扑克洗牌。抽取【{landlord_name}】为地主，公开底牌：【{' '.join(bottom_cards)}】。地主拥有优先出牌权！"
            }]
        }
        return self.get_client_state()

    def stream_step(self):
        """
        真·SSE实时流式推进一手牌。
        向调用者逐行 yield SSE 格式 JSON 字符串：data: {...}\n\n
        包含 60 秒充裕思考预算、429 限频自动重试与敌友针对性 Prompt 指令。
        """
        if self.state["status"] != "playing":
            yield f"data: {json.dumps({'event': 'idle', 'state': self.get_client_state()})}\n\n"
            return

        t_turn_start = time.time()
        curr_idx = self.state["current_turn"]
        player = self.state["players"][curr_idx]
        landlord_player = self.state["players"][self.state["landlord_idx"]]
        landlord_name = landlord_player["name"]

        # 上家与下家计算
        prev_player = self.state["players"][(curr_idx - 1) % 3]
        next_player = self.state["players"][(curr_idx + 1) % 3]

        # 敌友关系明确计算
        is_landlord = (player["role"] == "地主")
        prev_is_teammate = (not is_landlord) and (prev_player["role"] == "农民")
        next_is_teammate = (not is_landlord) and (next_player["role"] == "农民")

        # 当前是否为新一轮出牌 (两家都PASS或开局)
        is_free_turn = (self.state["pass_count"] >= 2 or not self.state["last_valid_play"])
        if is_free_turn:
            # 新一轮开始，清空上一轮各人面前的台面牌
            self.state["trick_played"] = {"0": None, "1": None, "2": None}
            last_play = []
            last_name = ""
            last_is_teammate = False
        else:
            last_play = self.state["last_valid_play"]
            last_name = self.state["last_valid_player_name"]
            last_is_teammate = (not is_landlord) and (last_name != landlord_name)

        sorted_hand = sort_cards(player["hand"])
        hand_before = list(player["hand"])

        # 广播出牌开始事件 (包含是否为新一轮出牌，供前端立即清空旧台面)
        yield f"data: {json.dumps({'event': 'start', 'seat_idx': curr_idx, 'model_name': player['name'], 'role': player['role'], 'is_free_turn': is_free_turn, 'timestamp': t_turn_start})}\n\n"

        provider_name = "智谱 AI (BigModel)" if player["provider"] == "zhipu" else "硅基流动 (SiliconFlow)"
        yield f"data: {json.dumps({'event': 'connecting', 'seat_idx': curr_idx, 'model_name': player['name'], 'provider': provider_name, 'msg': f'本地程序运行正常！已向 {provider_name} 发出网络请求，等待对方模型响应...' })}\n\n"

        # 1. 提取不带花色的手牌点数列表 (从大到小排列)
        pure_hand_ranks = [get_card_rank(c) for c in sorted_hand]
        pure_hand_text = " ".join(pure_hand_ranks)

        # 2. 裁判在本地预先计算出当前所有合法候选出牌组合 (单张、对子、顺子、连对、3带1、3带2、炸弹、王炸)
        legal_candidates = get_legal_candidates(player["hand"], last_play)
        options_block = "\n".join([f"选项 {opt['id']}: {opt['label']}" for opt in legal_candidates])

        # 3. 极简敌友与上下家描述 (不带烦琐的模型英文ID)
        prev_role_str = "队友 (农民)" if prev_is_teammate else ("对手 (地主)" if prev_player["role"] == "地主" else "对手 (农民)")
        next_role_str = "队友 (农民)" if next_is_teammate else ("对手 (地主)" if next_player["role"] == "地主" else "对手 (农民)")
        landlord_desc = "你本人" if is_landlord else f"你的对手 (剩 {len(landlord_player['hand'])} 张牌)"

        # 4. 局势与牌面描述 (纯点数，不带花色干扰)
        if is_free_turn:
            table_info = "【你拥有自由出牌权】（桌面上无牌，另外两家均已过牌。你必须主动打出一手合规牌，绝对不能不出 (PASS)！）"
        else:
            table_label = format_move_label(last_play)
            last_seat_idx = self.state["last_turn_idx"]
            last_hand_len = len(self.state["players"][last_seat_idx]["hand"]) if last_seat_idx >= 0 else 0
            rel_desc = "你的队友" if last_is_teammate else "你的对手 (地主)"
            table_info = f"【桌面上家打出的牌】：{table_label}（由【{rel_desc}】打出，该玩家手牌还剩 {last_hand_len} 张）"

        # 5. 精准战术指导 (防止农夫无脑挂机，指引接牌控场)
        if is_landlord:
            strategy_text = (
                "★ 你的战术指令：你是【地主】！其余两人都是你的敌人！\n"
                "你的目标是尽快把手牌全部出完。请从候选选项中选择能压制对手或最利于跑牌的组合！"
            )
        else:
            if is_free_turn:
                strategy_text = (
                    "★ 你的战术指令：你是【农民】！当前拥有自由出牌权，绝对不能不出 (PASS)！\n"
                    "建议优先打出顺子、连对、3带1/3带2、或小对子、单张小牌，快速走牌控场！"
                )
            elif last_is_teammate:
                teammate_left = len(self.state["players"][self.state["last_turn_idx"]]["hand"])
                if teammate_left <= 2:
                    strategy_text = (
                        f"★ 你的战术指令：你是【农民】！当前桌面上是由【你的队友】打出的牌！\n"
                        f"【🚨 终局警报】：你的队友只剩 {teammate_left} 张牌即将通关获胜！\n"
                        f"请务必果断选择【选项 A: 不出 (PASS)】！让队友顺利过牌，绝不能手痒抢队友牌权！"
                    )
                else:
                    strategy_text = (
                        f"★ 你的战术指令：你是【农民】！当前桌面上是由【你的队友】打出的牌！\n"
                        f"- 如果队友出的是 3-9 的小牌，且地主还没出牌，你如果手里有 10-K 的中大牌，可以主动选择大牌顶上去帮队友压制地主！\n"
                        f"- 如果队友出的已经是大牌（A、2、王），或者队友手牌很少（<=5张），请果断选择【选项 A: 不出 (PASS)】让队友过牌走牌，绝不要抢队友大牌！"
                    )
            else:
                strategy_text = (
                    "★ 你的战术指令：你是【农民】！当前桌面上是由【对手地主】打出的牌！\n"
                    "全力痛击敌人！如果你的候选选项里有能压住地主的牌，优先打出来压死地主！如果手牌确实打不过或保留实力，可选择【选项 A: 不出 (PASS)】！"
                )

        prompt = (
            f"你是斗地主选手。斗地主规则不看花色，只比点数大小与牌型！\n\n"
            f"【你的阵营与位置】\n"
            f"- 你的角色：【{player['role']}】\n"
            f"- 地主身份：【{landlord_desc}】\n"
            f"- 你的上家：【{prev_role_str}】（还剩 {len(prev_player['hand'])} 张牌）\n"
            f"- 你的下家：【{next_role_str}】（还剩 {len(next_player['hand'])} 张牌）\n\n"
            f"【你的当前手牌】（共 {len(sorted_hand)} 张，从大到小排列，不看花色）：\n"
            f"{pure_hand_text}\n\n"
            f"【当前局势】\n"
            f"{table_info}\n\n"
            f"{strategy_text}\n\n"
            f"★ 扑克牌点数与出牌核心铁律（大模型选手必须牢记）：\n"
            f"1.【严格点数大小，绝不可倒错】：\n"
            f"   大王 > 小王 > 2 > A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3\n"
            f"   警示：2 仅次于王牌，2 绝对大于 A/K/Q/J！绝不能产生「2比Q小」或「6能压K」的错觉！\n"
            f"2.【自由领牌权（无人出牌时）严禁盲甩王炸/大牌】：\n"
            f"   当由你自由开局领牌时，优先走掉自己手中的细碎散牌（如3、4、5、6）或多张组合！\n"
            f"   严禁在无人压制的情况下，首手就盲目砸出手中的王炸、炸弹或单张2！大牌控牌权是关键时刻救命与绝杀用的！\n"
            f"3.【组合套牌优先，杜绝无休止拆散单张互啄】：\n"
            f"   手中若有合法的三带二、三带一、顺子、连对或飞机，应优先成套打出，快速减少手牌张数！切勿把好好的多张牌型硬拆成小单张慢性自杀！\n"
            f"4.【赛点斩杀直觉】：\n"
            f"   当手牌只剩最后1手且属于合法选项时，必须直接打出绝杀赢下整场游戏，切勿犹豫或选不出！\n\n"
            f"★【裁判为你计算的合法候选出牌选项（你必须且只能从以下选项中选择一个）】：\n"
            f"{options_block}\n\n"
            f"请按以下两段结构进行回复：\n"
            f"【思考】\n"
            f"结合你的战术目标，简明分析选择哪个选项最有利于本方胜利...\n\n"
            f"【出牌决策】（必须在最后输出这两行）：\n"
            f"动作：打出（如果选不出写：不出）\n"
            f"牌面：选项B（可直接写选项代号如选项B，或写具体牌面如单张K）"
        )

        messages = [
            {"role": "system", "content": "你是一位真实的大模型斗地主职业选手。请分清敌友阵营与扑克点数大小（2次于王，3最小），遵循多张套牌优先与留大控场策略，给出原生真实的局势思考，并在末尾输出清晰的【出牌决策】。"},
            {"role": "user", "content": prompt}
        ]

        # 第一轮实时流式输出 (150秒单手总预算，带 429 自动重试)
        first_raw = ""
        is_timed_out = False
        timeout_reason = ""

        for kind, val in stream_model_api(player["provider"], player["model_id"], messages, max_wait_first_token=15, max_total_time=150, start_time=t_turn_start):
            if kind == "FIRST_TOKEN":
                yield f"data: {json.dumps({'event': 'first_token', 'seat_idx': curr_idx, 'latency': val, 'msg': f'对面大模型已响应 (首字耗时: {val}s)！正在全速流式推演...' })}\n\n"
            elif kind == "TOKEN":
                first_raw += val
                elapsed = round(time.time() - t_turn_start, 1)
                yield f"data: {json.dumps({'event': 'token', 'seat_idx': curr_idx, 'chunk': val, 'elapsed': elapsed})}\n\n"
            elif kind == "RETRY_429":
                att = val['attempt']
                m_att = val['max']
                w_sec = val['wait']
                msg_429 = f"遇到云端 429 频率限制，正在进行第 {att}/{m_att} 次自动重试 (等待 {w_sec}s)..."
                yield f"data: {json.dumps({'event': 'retry_429', 'seat_idx': curr_idx, 'attempt': att, 'max': m_att, 'wait': w_sec, 'msg': msg_429})}\n\n"
            elif kind == "TIMEOUT_LIMIT":
                first_raw += val
                is_timed_out = True
                timeout_reason = val.strip()
                yield f"data: {json.dumps({'event': 'timeout', 'seat_idx': curr_idx, 'reason': timeout_reason})}\n\n"
            elif kind == "NET_ERROR":
                first_raw += val
                is_timed_out = True
                timeout_reason = val.strip()
                yield f"data: {json.dumps({'event': 'net_error', 'seat_idx': curr_idx, 'reason': f'对面大模型网络异常或等待超时 ({val.strip()})，本地程序正常！裁判强制介入！'})}\n\n"

        if not is_timed_out and len(first_raw.strip()) < 5:
            is_timed_out = True
            timeout_reason = "对面大模型未返回有效思考内容"

        raw_thinking = first_raw
        rethink_occurred = False
        intended_play = []

        if is_timed_out:
            yield f"data: {json.dumps({'event': 'timeout', 'seat_idx': curr_idx, 'reason': f'【裁判介入】：{timeout_reason}，强制代选合规出牌！'})}\n\n"
            actual_play = find_valid_move(player["hand"], last_play)
            is_legal = False
            illegal_reason = f"思考超时或连接异常 ({timeout_reason})"
            raw_thinking += f"\n\n[⏱️ 裁判超时裁定]: 选手思考超出 60 秒时限，裁判介入并执行规则动作！"
        else:
            intended_play = parse_natural_play(first_raw, player["hand"], legal_candidates)
            is_legal, illegal_reason = check_cards_validity(intended_play, player["hand"], last_play)

            # 若违规，触发实时二度反思 (仍受总时长 60s 约束)
            if not is_legal:
                rethink_occurred = True
                yield f"data: {json.dumps({'event': 'rejected', 'seat_idx': curr_idx, 'reason': illegal_reason, 'intended': intended_play})}\n\n"

                reject_prompt = (
                    f"【🚨 裁判违规拦截警告】\n"
                    f"你刚才企图打出的牌【{' '.join(intended_play) if intended_play else '空'}】被裁判程序拦截！\n"
                    f"具体违规原因：{illegal_reason}。\n"
                    f"★ 请必须且只能从以下裁判为你计算的合法候选选项中挑选一个打出：\n"
                    f"{options_block}\n\n"
                    f"请立即给出简明反思，并严格在最后两行输出决策：\n"
                    f"【思考】\n"
                    f"从合法选项中挑选手牌...\n"
                    f"【出牌决策】\n"
                    f"动作：打出（如果选不出写：不出）\n"
                    f"牌面：选项B"
                )
                messages.append({"role": "assistant", "content": first_raw})
                messages.append({"role": "user", "content": reject_prompt})

                second_raw = ""
                yield f"data: {json.dumps({'event': 'rethink_start', 'seat_idx': curr_idx})}\n\n"
                for kind, val in stream_model_api(player["provider"], player["model_id"], messages, max_wait_first_token=12, max_total_time=150, start_time=t_turn_start):
                    if kind == "TOKEN":
                        second_raw += val
                        elapsed = round(time.time() - t_turn_start, 1)
                        yield f"data: {json.dumps({'event': 'rethink_token', 'seat_idx': curr_idx, 'chunk': val, 'elapsed': elapsed})}\n\n"
                    elif kind == "RETRY_429":
                        att = val['attempt']
                        m_att = val['max']
                        w_sec = val['wait']
                        msg_429 = f"遇到云端 429 频率限制，正在进行第 {att}/{m_att} 次自动重试 (等待 {w_sec}s)..."
                        yield f"data: {json.dumps({'event': 'retry_429', 'seat_idx': curr_idx, 'attempt': att, 'max': m_att, 'wait': w_sec, 'msg': msg_429})}\n\n"
                    elif kind in ["TIMEOUT_LIMIT", "NET_ERROR"]:
                        second_raw += val
                        yield f"data: {json.dumps({'event': 'timeout', 'seat_idx': curr_idx, 'reason': '反思超时或网络异常，裁判直接代选合法出牌！'})}\n\n"

                second_intended = parse_natural_play(second_raw, player["hand"], legal_candidates)
                second_legal, second_reason = check_cards_validity(second_intended, player["hand"], last_play)

                raw_thinking += f"\n\n[🚨 裁判驳回后重思]:\n{second_raw}"
                intended_play = second_intended
                is_legal = second_legal
                illegal_reason = second_reason

            # 最终执行确认
            if is_legal:
                actual_play = intended_play
            else:
                actual_play = find_valid_move(player["hand"], last_play)

        pattern_type, _, _ = parse_card_pattern(actual_play)

        if actual_play:
            for c in actual_play:
                if c in player["hand"]:
                    player["hand"].remove(c)
            self.state["last_valid_play"] = actual_play
            self.state["last_valid_player_name"] = player["name"]
            self.state["pass_count"] = 0
            self.state["last_action_type"] = pattern_type
            action_desc = f"打出【{' '.join(actual_play)}】"
            # 记录席位台面牌
            self.state["trick_played"][str(curr_idx)] = {"cards": actual_play, "action": "打出", "role": player["role"]}
        else:
            self.state["pass_count"] += 1
            self.state["last_action_type"] = "PASS"
            action_desc = "不出 (PASS)"
            # 记录席位台面不出
            self.state["trick_played"][str(curr_idx)] = {"cards": [], "action": "不出", "role": player["role"]}

        total_cost = round(time.time() - t_turn_start, 2)
        self.state["last_turn_idx"] = curr_idx
        player["last_action"] = action_desc
        player["last_thinking"] = raw_thinking
        player["is_legal_last"] = is_legal
        player["illegal_reason_last"] = illegal_reason

        # 裁判公证记录
        if is_legal:
            log_item = {
                "time": f"第 {len(self.state['turns_record']) + 1} 手 ({total_cost}s)",
                "tag": "规则通过",
                "text": f"【{player['name']}】({player['role']}) {action_desc}。经程序裁判核验：合规放行！(耗时: {total_cost}s)"
            }
        else:
            log_item = {
                "time": f"第 {len(self.state['turns_record']) + 1} 手 ({total_cost}s)",
                "tag": "违规拦截",
                "text": f"🚨【{player['name']}】出牌违规: {illegal_reason}。强制裁判执行：{action_desc}！(耗时: {total_cost}s)"
            }
        self.state["system_logs"].append(log_item)

        turn_data = {
            "turn_index": len(self.state["turns_record"]) + 1,
            "seat": player["seat"],
            "model_name": player["name"],
            "role": player["role"],
            "hand_before": hand_before,
            "table_cards_before": last_play,
            "intended_play": intended_play,
            "is_legal": is_legal,
            "illegal_reason": illegal_reason,
            "actual_play": actual_play,
            "hand_remain": len(player["hand"]),
            "duration_sec": total_cost,
            "raw_thinking": raw_thinking
        }
        self.state["turns_record"].append(turn_data)

        if len(player["hand"]) == 0:
            self.state["status"] = "game_over"
            self.state["winner"] = player["name"]
            self.state["winner_role"] = player["role"]
            self.export_record_to_file()
        else:
            self.state["current_turn"] = (curr_idx + 1) % 3

        # 发送完成及更新后状态（携带席位独立台面出牌信息与真实耗时）
        yield f"data: {json.dumps({'event': 'finish', 'actual_play': actual_play, 'is_legal': is_legal, 'rethink_occurred': rethink_occurred, 'duration': total_cost, 'trick_played': self.state['trick_played'], 'state': self.get_client_state()})}\n\n"

    def step(self):
        """同步出牌接口 (消费流式生成器并返回最终状态)"""
        last_state = self.get_client_state()
        for chunk in self.stream_step():
            if '"event": "finish"' in chunk or '"event": "idle"' in chunk:
                try:
                    payload = json.loads(chunk.strip()[6:])
                    last_state = payload.get('state', last_state)
                except:
                    pass
        return last_state

    def export_record_to_file(self):
        record_dump = {
            "game_id": self.state["game_id"],
            "landlord": self.state["players"][self.state["landlord_idx"]]["name"] if self.state["players"] else "未知",
            "bottom_cards": self.state["bottom_cards"],
            "winner": self.state["winner"],
            "winner_role": self.state["winner_role"],
            "players_summary": [
                {"seat": p["seat"], "model": p["name"], "role": p["role"], "cards_left": len(p["hand"])}
                for p in self.state["players"]
            ],
            "turns": self.state["turns_record"]
        }
        with open(RECORD_PATH, 'w', encoding='utf-8') as f:
            json.dump(record_dump, f, ensure_ascii=False, indent=2)

        # 同时持久化保存至 records_raw 文件夹，支持赛后复盘室随心选谱
        try:
            raw_dir = os.path.join(os.path.dirname(__file__), 'records_raw')
            os.makedirs(raw_dir, exist_ok=True)
            ts_str = time.strftime("%Y%m%d_%H%M%S")
            winner_str = self.state.get("winner_role", "peasant") or "game"
            turns_cnt = len(self.state.get("turns_record", []))
            filename = f"game_{ts_str}_{turns_cnt}手_{winner_str}胜.json"
            full_path = os.path.join(raw_dir, filename)
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(record_dump, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存 records_raw 失败:", e)

    def get_client_state(self):
        return copy.deepcopy(self.state)
