"""
斗地主核心规则与牌型引擎
包含 54 张牌洗牌、发牌、牌型识别、比牌规则校验及防作弊合法性校验。
"""
import random
from collections import Counter

# 牌面点数权重表
RANK_VALUES = {
    '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15,
    '小王': 16, '大王': 17
}
VALUE_TO_RANK = {v: k for k, v in RANK_VALUES.items()}

SUITS = ['♠', '♥', '♣', '♦']
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

def create_deck():
    """生成标准 54 张扑克牌"""
    deck = []
    for r in RANKS:
        for s in SUITS:
            deck.append(f"{s}{r}")
    deck.append("小王")
    deck.append("大王")
    return deck

def get_card_rank(card):
    """提取牌的面值"""
    if card in ["小王", "大王"]:
        return card
    return card[1:]

def get_card_value(card):
    """获取牌的大小数值"""
    return RANK_VALUES[get_card_rank(card)]

def sort_cards(cards):
    """按牌面大小从大到小排序"""
    return sorted(cards, key=lambda c: get_card_value(c), reverse=True)

class CardType:
    PASS = "PASS"
    SINGLE = "SINGLE"                  # 单张
    PAIR = "PAIR"                      # 对子
    TRIPLE = "TRIPLE"                  # 三张
    TRIPLE_ONE = "TRIPLE_ONE"          # 三带一
    TRIPLE_TWO = "TRIPLE_TWO"          # 三带二
    STRAIGHT = "STRAIGHT"              # 顺子 (>=5张)
    CONSECUTIVE_PAIRS = "CONSEC_PAIRS" # 连对 (>=3对)
    BOMB = "BOMB"                      # 炸弹
    ROCKET = "ROCKET"                  # 王炸 / 火箭
    INVALID = "INVALID"                # 不合规

def parse_card_pattern(cards):
    """解析牌型，返回 (CardType, primary_value, length)"""
    if not cards:
        return (CardType.PASS, 0, 0)

    n = len(cards)
    ranks = [get_card_rank(c) for c in cards]
    values = sorted([RANK_VALUES[r] for r in ranks])
    counts = Counter(values)
    count_items = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    # 1. 王炸
    if n == 2 and 16 in values and 17 in values:
        return (CardType.ROCKET, 17, 2)

    # 2. 单张
    if n == 1:
        return (CardType.SINGLE, values[0], 1)

    # 3. 对子
    if n == 2 and values[0] == values[1]:
        return (CardType.PAIR, values[0], 2)

    # 4. 三张
    if n == 3 and values[0] == values[1] == values[2]:
        return (CardType.TRIPLE, values[0], 3)

    # 5. 炸弹 (4张同点数)
    if n == 4 and count_items[0][1] == 4:
        return (CardType.BOMB, count_items[0][0], 4)

    # 6. 三带一 (4张: 3+1)
    if n == 4 and count_items[0][1] == 3:
        return (CardType.TRIPLE_ONE, count_items[0][0], 4)

    # 7. 三带二 (5张: 3+2)
    if n == 5 and count_items[0][1] == 3 and count_items[1][1] == 2:
        return (CardType.TRIPLE_TWO, count_items[0][0], 5)

    # 8. 顺子 (>=5张连续单张，不能包含2和王)
    if n >= 5 and max(values) <= 14 and len(set(values)) == n:
        if values[-1] - values[0] == n - 1:
            return (CardType.STRAIGHT, values[-1], n)

    # 9. 连对 (>=6张连续对子，3对及以上)
    if n >= 6 and n % 2 == 0:
        pair_vals = [k for k, v in counts.items() if v == 2]
        if len(pair_vals) * 2 == n and max(pair_vals) <= 14:
            sorted_pairs = sorted(pair_vals)
            if sorted_pairs[-1] - sorted_pairs[0] == len(sorted_pairs) - 1:
                return (CardType.CONSECUTIVE_PAIRS, sorted_pairs[-1], n)

    return (CardType.INVALID, 0, 0)

def can_beat(new_cards, last_cards):
    """
    判断 new_cards 能否大过 last_cards。
    如果 last_cards 为空/PASS，只要 new_cards 是合规牌型即可。
    """
    new_type, new_val, new_len = parse_card_pattern(new_cards)
    if new_type == CardType.INVALID:
        return False, "牌型不合规"

    # 如果上次出牌是过，只要是合法牌型就能出
    if not last_cards:
        if new_type == CardType.PASS:
            return False, "不能空过出牌"
        return True, "有效出牌"

    last_type, last_val, last_len = parse_card_pattern(last_cards)

    # 自己过牌
    if new_type == CardType.PASS:
        return True, "不出/过"

    # 王炸天下第一
    if new_type == CardType.ROCKET:
        return True, "王炸大过一切！"

    # 对方是王炸，任何牌都管不起
    if last_type == CardType.ROCKET:
        return False, "对方是王炸，无法压制"

    # 炸弹可以压制非炸弹牌型
    if new_type == CardType.BOMB:
        if last_type != CardType.BOMB:
            return True, "炸弹压制普通牌型"
        else:
            return (new_val > last_val), "同为炸弹，比点数大小"

    # 普通牌型必须类型相同且张数相同
    if new_type != last_type or new_len != last_len:
        return False, f"牌型不匹配（需要 {last_type}，张数 {last_len}）"

    return (new_val > last_val), "点数比上家大" if new_val > last_val else "点数不够大"

def generate_all_valid_moves(hand):
    """
    根据手牌生成所有合法的出牌组合 (返回卡牌列表的列表)
    """
    moves = []
    counts = Counter([get_card_rank(c) for c in hand])
    unique_ranks = sorted(counts.keys(), key=lambda r: RANK_VALUES[r])

    def pick_cards(r, num):
        matching = [c for c in hand if get_card_rank(c) == r]
        return matching[:num]

    # 1. 王炸
    if '小王' in hand and '大王' in hand:
        moves.append(['小王', '大王'])

    # 2. 炸弹 (4张)
    for r in unique_ranks:
        if counts[r] == 4:
            moves.append(pick_cards(r, 4))

    # 3. 顺子 (>=5张连续单张，点数 3-A)
    straight_candidates = [r for r in unique_ranks if 3 <= RANK_VALUES[r] <= 14]
    val_set = set(RANK_VALUES[r] for r in straight_candidates)
    for length in range(5, 13):
        for start_val in range(3, 15 - length + 1):
            if all((start_val + i) in val_set for i in range(length)):
                st = []
                for i in range(length):
                    st.extend(pick_cards(VALUE_TO_RANK[start_val + i], 1))
                moves.append(st)

    # 4. 连对 (>=3对连续对子，点数 3-A)
    pair_candidates = [r for r in unique_ranks if counts[r] >= 2 and 3 <= RANK_VALUES[r] <= 14]
    pair_val_set = set(RANK_VALUES[r] for r in pair_candidates)
    for pair_len in range(3, 11):
        for start_val in range(3, 15 - pair_len + 1):
            if all((start_val + i) in pair_val_set for i in range(pair_len)):
                cp = []
                for i in range(pair_len):
                    cp.extend(pick_cards(VALUE_TO_RANK[start_val + i], 2))
                moves.append(cp)

    # 5. 三带二
    for r in unique_ranks:
        if counts[r] >= 3:
            triplet = pick_cards(r, 3)
            for kicker in unique_ranks:
                if kicker != r and counts[kicker] >= 2:
                    moves.append(triplet + pick_cards(kicker, 2))

    # 6. 三带一
    for r in unique_ranks:
        if counts[r] >= 3:
            triplet = pick_cards(r, 3)
            for kicker in unique_ranks:
                if kicker != r:
                    moves.append(triplet + pick_cards(kicker, 1))

    # 7. 三张
    for r in unique_ranks:
        if counts[r] >= 3:
            moves.append(pick_cards(r, 3))

    # 8. 对子
    for r in unique_ranks:
        if counts[r] >= 2:
            moves.append(pick_cards(r, 2))

    # 9. 单张
    for r in unique_ranks:
        moves.append(pick_cards(r, 1))

    return moves

def format_move_label(cards):
    """为出牌组合生成清晰的人性化中文标签 (纯点数，不带花色)"""
    c_type, val, length = parse_card_pattern(cards)
    ranks = [get_card_rank(c) for c in cards]

    if c_type == CardType.ROCKET:
        return "打出王炸【小王 大王】(🚀最大王炸)"
    elif c_type == CardType.BOMB:
        return f"打出炸弹【4个{ranks[0]}】(💣炸弹)"
    elif c_type == CardType.SINGLE:
        return f"打出单张【{ranks[0]}】"
    elif c_type == CardType.PAIR:
        return f"打出对子【{ranks[0]} {ranks[1]}】"
    elif c_type == CardType.TRIPLE:
        return f"打出三张【{ranks[0]} {ranks[1]} {ranks[2]}】"
    elif c_type == CardType.TRIPLE_ONE:
        counts = Counter(ranks)
        triplet_r = [k for k, v in counts.items() if v == 3][0]
        kicker_r = [k for k, v in counts.items() if v == 1][0]
        return f"打出【3个{triplet_r}带{kicker_r}】"
    elif c_type == CardType.TRIPLE_TWO:
        counts = Counter(ranks)
        triplet_r = [k for k, v in counts.items() if v == 3][0]
        pair_r = [k for k, v in counts.items() if v == 2][0]
        return f"打出【3个{triplet_r}带对{pair_r}】"
    elif c_type == CardType.STRAIGHT:
        return f"打出顺子【{'-'.join(ranks)}】({length}张连牌)"
    elif c_type == CardType.CONSECUTIVE_PAIRS:
        distinct_ranks = []
        for r in ranks:
            if r not in distinct_ranks:
                distinct_ranks.append(r)
        return f"打出连对【{'-'.join(distinct_ranks)}】({length}张连对)"
    else:
        return f"打出【{' '.join(ranks)}】"

def get_legal_candidates(hand, last_cards):
    """
    计算当前玩家的所有合法候选出牌选项列表。
    返回: options 列表，每个元素为:
    {"id": "A", "label": "...", "ranks": [...], "cards": [...], "type": ...}
    """
    all_moves = generate_all_valid_moves(hand)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if last_cards:
        # 跟牌态：必须能大过 last_cards
        beat_moves = [m for m in all_moves if can_beat(m, last_cards)[0]]
        options = []
        # 选项 A 始终为 不出 (PASS)
        options.append({
            "id": "A",
            "label": "不出 (PASS)",
            "ranks": [],
            "cards": [],
            "type": CardType.PASS
        })
        for i, m in enumerate(beat_moves):
            if i + 1 >= len(letters):
                break
            opt_id = letters[i + 1]
            c_type, _, _ = parse_card_pattern(m)
            options.append({
                "id": opt_id,
                "label": format_move_label(m),
                "ranks": [get_card_rank(c) for c in m],
                "cards": m,
                "type": c_type
            })
        return options
    else:
        # 自由出牌态：不能不出，展示多样化的合法首发组合
        options = []
        # 按类型优先级与牌张从小到大呈现
        for i, m in enumerate(all_moves):
            if i >= len(letters):
                break
            opt_id = letters[i]
            c_type, _, _ = parse_card_pattern(m)
            options.append({
                "id": opt_id,
                "label": format_move_label(m),
                "ranks": [get_card_rank(c) for c in m],
                "cards": m,
                "type": c_type
            })
        return options

def find_valid_move(hand, last_cards):
    """
    AI 启发式保底机制：从合法选项中选出最合理的第一手牌
    """
    candidates = get_legal_candidates(hand, last_cards)
    if not candidates:
        return []
    if not last_cards:
        # 自由出牌：选单张最小牌或对子最小牌
        for c in reversed(candidates):
            if c['type'] in [CardType.SINGLE, CardType.PAIR]:
                return c['cards']
        return candidates[0]['cards']
    else:
        # 跟牌：若有能压制的牌，选非炸弹的最小压制牌；若没有，选不出
        playable = [c for c in candidates if c['type'] != CardType.PASS]
        if playable:
            # 优先选非炸弹的普通牌型
            normal = [c for c in playable if c['type'] not in [CardType.BOMB, CardType.ROCKET]]
            if normal:
                return normal[-1]['cards'] # 取列表中点数较小的那手
            return playable[-1]['cards']
        return []
