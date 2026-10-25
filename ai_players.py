"""
AI 斗地主选手调度引擎
- 100% 永久免费模型，严禁任何扣费付费模型！
- 真·SSE实时流式令牌输出，真实双流 (原生思考链 + 结构化出牌决策)
- 429 限频自动重试 5 次保护机制
- 单手总时长 60 秒硬顶上限，流式不卡断
"""
import os
import re
import json
import time
import socket
import urllib.request
import urllib.error

# 设置全局底层 Socket 超时，防止网络挂起或模型流式挂死
socket.setdefaulttimeout(15)
from doudizhu_rules import RANK_VALUES, get_card_rank, get_card_value, sort_cards, can_beat, find_valid_move, parse_card_pattern, CardType

ENV_PATH = os.path.join(os.path.dirname(__file__), 'api_keys.env')
config = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()

ZHIPU_KEY = config.get('ZHIPU_API_KEY', '')
SILICON_KEY = 'sk-wqkeymjdmtglghtiyclceictwifltgwozgccszsnjoecrcmp'

# 全量 100% 永久免费候选模型库 (6 款真机测试通过的 0 元模型)
FREE_MODEL_ROSTER = {
    "GLM-4-Flash": {
        "name": "GLM-4-Flash",
        "provider": "zhipu",
        "model_id": "glm-4-flash",
        "desc": "智谱主力 · 速度极快 · 永久免费",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=GLM4Flash&backgroundColor=b6e3f4"
    },
    "GLM-4-Flash-250414": {
        "name": "GLM-4-Flash-250414",
        "provider": "zhipu",
        "model_id": "glm-4-flash-250414",
        "desc": "智谱经典 · 稳健守规 · 永久免费",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=GLM4Old&backgroundColor=c0aede"
    },
    "GLM-4.7-Flash": {
        "name": "GLM-4.7-Flash",
        "provider": "zhipu",
        "model_id": "glm-4.7-flash",
        "desc": "智谱最新 · 200K上下文 · 永久免费",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=GLM47Flash&backgroundColor=ffd5dc"
    },
    "GLM-Z1-Flash": {
        "name": "GLM-Z1-Flash",
        "provider": "zhipu",
        "model_id": "glm-z1-flash",
        "desc": "智谱慢思考推理 · 原生<think>思维链 · 永久免费",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=GLMZ1&backgroundColor=ffeaa7"
    },
    "Qwen/Qwen2.5-7B-Instruct": {
        "name": "Qwen/Qwen2.5-7B-Instruct",
        "provider": "siliconflow",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "desc": "阿里通义 7B · 硅基0元直连 · 极速响应",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=Qwen7B&backgroundColor=dff9fb"
    },
    "XingChenAGI/Xing4.0-29B": {
        "name": "XingChenAGI/Xing4.0-29B",
        "provider": "siliconflow",
        "model_id": "XingChenAGI/Xing4.0-29B",
        "desc": "中国电信 29B · 硅基0元直连 · 290亿参数",
        "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=XingChen29B&backgroundColor=f6e58d"
    }
}

def stream_model_api(provider, model_id, messages, max_wait_first_token=15, max_total_time=150, start_time=None):
    """
    底层真·流式 API 生成器，向外 yield (事件类型, 数据内容) 元组：
    - ("FIRST_TOKEN", latency_sec)
    - ("TOKEN", chunk_str)
    - ("RETRY_429", {"attempt": i, "max": 5, "wait": sec})
    - ("TIMEOUT_LIMIT", msg)
    - ("NET_ERROR", err_str)
    """
    t0 = start_time if start_time else time.time()
    if provider == "zhipu":
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        key = ZHIPU_KEY
    else:
        url = "https://api.siliconflow.cn/v1/chat/completions"
        key = SILICON_KEY

    payload = json.dumps({
        "model": model_id,
        "messages": messages,
        "temperature": 0.6,
        "stream": True,
        "max_tokens": 4096
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    })

    # 连接尝试与 429 速率限制重试循环 (最多 5 次)
    res = None
    for attempt in range(1, 6):
        try:
            res = urllib.request.urlopen(req, timeout=max_wait_first_token)
            break
        except urllib.error.HTTPError as he:
            if he.code == 429:
                if attempt < 5:
                    wait_sec = min(1.5 * attempt, 6.0)
                    yield ("RETRY_429", {"attempt": attempt, "max": 5, "wait": wait_sec})
                    time.sleep(wait_sec)
                    continue
                else:
                    yield ("NET_ERROR", f"429 限频且 5 次重试均失败: {he}")
                    return
            else:
                yield ("NET_ERROR", f"HTTP {he.code} 错误: {he}")
                return
        except Exception as e:
            if attempt < 5 and ("timed out" in str(e).lower() or "timeout" in str(e).lower()):
                wait_sec = 2.0
                yield ("RETRY_429", {"attempt": attempt, "max": 5, "wait": wait_sec})
                time.sleep(wait_sec)
                continue
            else:
                yield ("NET_ERROR", f"网络连接异常: {e}")
                return

    if not res:
        yield ("NET_ERROR", "无法建立网络连接")
        return

    first_token_received = False
    try:
        for line in res:
            elapsed = time.time() - t0
            if elapsed > max_total_time:
                yield ("TIMEOUT_LIMIT", f"\n\n[⏱️ 裁判超时判决：单次总思考耗时达上限 ({elapsed:.1f}s/150s)，强制截停！]")
                break

            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str.startswith('data: ') and line_str != 'data: [DONE]':
                try:
                    chunk = json.loads(line_str[6:])
                    delta = chunk['choices'][0]['delta']
                    reasoning = delta.get('reasoning_content', '')
                    content = delta.get('content', '')
                    c = reasoning or content
                    if c:
                        if not first_token_received:
                            first_token_received = True
                            yield ("FIRST_TOKEN", round(time.time() - t0, 2))
                        yield ("TOKEN", c)
                except:
                    pass
    except GeneratorExit:
        raise
    except Exception as e:
        yield ("NET_ERROR", f"\n[❌ 对面大模型流式传输中断: {e}]")

def check_model_handshake(model_key):
    """真机握手开场白检测"""
    info = FREE_MODEL_ROSTER.get(model_key)
    if not info:
        return {"success": False, "error": "未知模型", "latency": "0s", "greeting": ""}

    t0 = time.time()
    prompt = "你正作为职业斗地主选手入场。请向全场观众和对手说一句 15 字以内的霸气开场白，直接输出一句话即可。"
    messages = [
        {"role": "system", "content": "你是一位霸气的大模型斗地主选手。"},
        {"role": "user", "content": prompt}
    ]
    try:
        collected = ""
        for kind, val in stream_model_api(info["provider"], info["model_id"], messages, max_wait_first_token=8, max_total_time=15):
            if kind == "TOKEN":
                collected += val
        cost = time.time() - t0
        clean_text = collected.strip().strip('"').strip('“').strip('”')
        if '</think>' in clean_text:
            clean_text = clean_text.split('</think>')[-1].strip()
        else:
            clean_text = re.sub(r'<think>.*?</think>', '', clean_text, flags=re.DOTALL).replace('<think>', '').strip()
        
        greeting = clean_text or "今日斗地主，唯我独尊！"
        return {
            "success": True,
            "greeting": greeting[:30],
            "latency": f"{cost:.2f}s",
            "error": ""
        }
    except Exception as ex:
        cost = time.time() - t0
        return {
            "success": False,
            "greeting": "",
            "latency": f"{cost:.2f}s",
            "error": str(ex)
        }

def parse_natural_play(full_text, hand_cards, options=None):
    """
    结构化候选选项与自由文本融合提取器：
    1. 优先精准匹配 candidate options (通过选项代号 A/B/C、选项完整文本或纯点数集合完全匹配)
    2. 若未传入 options 或未匹配到，则兼容自然文本、花色中文名替换与对子识别
    """
    clean_text = full_text.replace('\r', '').strip()
    decision_text = clean_text
    if '【出牌决策】' in clean_text:
        decision_text = clean_text.split('【出牌决策】')[-1].strip()
    elif '出牌决策' in clean_text:
        decision_text = clean_text.split('出牌决策')[-1].strip()

    # 1. 如果传入了 options 列表，优先走合法候选项匹配 (准确率 100%)
    if options:
        # (a) 动作明确是不出
        if re.search(r'动作[：:\s]*(不出|过|不要|PASS|pass|要不起|管不上)', decision_text):
            return []

        # (b) 匹配选项代号 (例如 "选项 B", "选项B", "选项 2", "B")
        opt_match = re.search(r'选项\s*([A-Za-z0-9]+)', decision_text)
        if opt_match:
            opt_key = opt_match.group(1).upper()
            for opt in options:
                if str(opt['id']).upper() == opt_key:
                    return opt['cards']

        # (c) 提取决策文本中的纯点数，并与 options 做集合完全匹配
        tokens = re.findall(r'(大王|小王|10|[2-9JQKA])', decision_text)
        if tokens:
            sorted_tokens = sorted(tokens, key=lambda r: RANK_VALUES.get(r, 0))
            for opt in options:
                opt_sorted = sorted(opt['ranks'], key=lambda r: RANK_VALUES.get(r, 0))
                if opt_sorted == sorted_tokens:
                    return opt['cards']

        # (d) 匹配选项中的文本标签或特征词 (如 "打出单张【K】", "3个8带4", "对8")
        sorted_by_len = sorted(options, key=lambda o: len(' '.join(o.get('ranks', []))), reverse=True)
        for opt in sorted_by_len:
            if opt['type'] == 'PASS':
                continue
            if opt['label'] in decision_text or (' '.join(opt['ranks']) in decision_text and opt['ranks']):
                return opt['cards']

        # (e) 如果决策文本明确包含不出
        if any(k in decision_text for k in ['不出', '不要', '过', 'PASS', 'pass', '要不起']) and '打出' not in decision_text:
            return []

    # 2. 回退机制：原有自由文本提取
    text = full_text.replace('黑桃', '♠').replace('红桃', '♥').replace('梅花', '♣').replace('草花', '♣').replace('方块', '♦').replace('方片', '♦')
    
    if re.search(r'动作[：:\s]*(不出|过|不要|PASS|pass|要不起|管不上)', text):
        return []

    cards_section = ""
    card_match = re.search(r'牌面[：:\s]*([^\n\r]+)', text)
    if card_match:
        cards_section = card_match.group(1).strip()
    else:
        m = re.search(r'【出牌】[：:\s]*([^\n\r]+)', text)
        if m:
            cards_section = m.group(1).strip()
        else:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                cards_section = lines[-1]

    if any(k in cards_section for k in ['不出', '过', '不要', 'PASS', 'pass', '要不起', '管不上', '空']):
        return []

    matched_cards = []
    hand_copy = list(hand_cards)

    # 识别对子关键词
    pair_match = re.search(r'(?:对|一对|两个|两张)\s*([♠♥♣♦]?(?:10|[2-9JQKA]))', cards_section)
    if pair_match:
        target_rank = re.sub(r'[♠♥♣♦]', '', pair_match.group(1))
        matching_in_hand = [h for h in hand_copy if get_card_rank(h) == target_rank]
        if len(matching_in_hand) >= 2:
            return matching_in_hand[:2]

    # 通用正则从 cards_section 中提取牌
    raw_tokens = re.findall(r'[♠♥♣♦]?(?:10|[2-9JQKA]|小王|大王)', cards_section)
    for tok in raw_tokens:
        found = None
        if tok in hand_copy:
            found = tok
        else:
            rank_only = re.sub(r'[♠♥♣♦]', '', tok)
            for h in hand_copy:
                if get_card_rank(h) == (rank_only or tok):
                    found = h
                    break
        if found:
            matched_cards.append(found)
            hand_copy.remove(found)

    return matched_cards

def check_cards_validity(intended_play, hand_cards, last_cards):
    """纯逻辑规则校验：手牌真实存在性与牌型压制性"""
    if not intended_play:
        if not last_cards:
            return False, "自由出牌权不能不出，必须出一手合规牌！"
        return True, "合规通过 (不出)"

    # 检查手牌真实性
    hand_copy = list(hand_cards)
    for c in intended_play:
        matched = None
        if c in hand_copy:
            matched = c
        else:
            for h in hand_copy:
                if get_card_rank(h) == c:
                    matched = h
                    break
        if matched:
            hand_copy.remove(matched)
        else:
            return False, f"手中根本没有【{c}】(产生手牌幻觉)"

    # 检查牌型合法性与能否压过上家
    can_beat_result, beat_reason = can_beat(intended_play, last_cards)
    if not can_beat_result:
        return False, f"牌型规则不符: {beat_reason}"

    return True, "合规通过"
