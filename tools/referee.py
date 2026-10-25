"""
金牌主裁判兼荷官兼名嘴解说 (Gemini 3.8 Flash High 真机大模型驱动)
每回合通过 API 实时调用大模型生成纯正、犀利、幽默的粤语/国语双语现场解说与执法点评！
"""
import os
import json
import random
import urllib.request

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

class GeminiReferee:
    def __init__(self):
        self.name = "Gemini 3.8 Flash (金牌主裁判)"
        self.badge = "🎙️ 实时大模型驱动"

    def _call_live_ai(self, prompt, fallback_func):
        """调用免费大模型实时生成裁判解说，超时则启用保底库"""
        if not ZHIPU_KEY:
            return fallback_func()

        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        payload = json.dumps({
            "model": "glm-4-flash",
            "messages": [
                {
                    "role": "system",
                    "content": "你是第一届【AI 斗地主薯仔争霸赛】的金牌特级主裁判兼名嘴解说【Gemini 3.8 Flash High】。你精明强干、眼光毒辣、精通粤语白话与普通话。面对选手出牌，你要么犀利吐槽、要么抓偷鸡作弊，语言充满戏剧性与幽默感。每次回复控制在 35-50 字之间，直接说台词，不要带格式。"
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 100
        }).encode('utf-8')

        try:
            req = urllib.request.Request(url, data=payload, headers={
                "Authorization": f"Bearer {ZHIPU_KEY}",
                "Content-Type": "application/json"
            })
            res = urllib.request.urlopen(req, timeout=3)
            data = json.loads(res.read().decode('utf-8'))
            return data['choices'][0]['message']['content'].strip()
        except:
            return fallback_func()

    def opening_speech(self, landlord_name, bottom_cards):
        """开局报幕与底牌揭晓"""
        prompt = f"比赛刚开局，选手【{landlord_name}】抢到了地主，开出的3张底牌是【{' '.join(bottom_cards)}】。请说一段热情澎湃、带点调侃的开场白！"
        def fallback():
            quotes = [
                f"各位观众大家好！我系全场唯一保持清醒嘅主裁判 Gemini 3.8！今晚地主由【{landlord_name}】强行抢低！底牌开出：【{' '.join(bottom_cards)}】！比赛正式开打！",
                f"哔哔——！荷官已就位，洗牌完毕！【{landlord_name}】盲目自信抢到地主！底牌开出：【{' '.join(bottom_cards)}】！看看两位农民能否联手翻天！"
            ]
            return random.choice(quotes)
        return self._call_live_ai(prompt, fallback)

    def comment_play(self, player_name, role, played_cards, was_cheated, hand_remain, pattern_type):
        """每手牌的犀利点评"""
        action = f"打出【{' '.join(played_cards)}】({pattern_type})" if played_cards else "选择了不出(PASS)"
        cheat_info = "【作弊警报：该选手产生了幻觉，手中根本没有这几张牌，被裁判当场抓获并强制合规修正！】" if was_cheated else "正常出牌"

        prompt = (
            f"选手【{player_name}】({role})刚刚{action}。\n"
            f"作弊状态：{cheat_info}\n"
            f"剩余手牌张数：{hand_remain}张。\n"
            f"请以 Gemini 3.8 金牌裁判身份，现场给出一段尖锐搞笑的实时点评！"
        )

        def fallback():
            if was_cheated:
                return f"🚨 哔哔！裁判吹哨抓包！【{player_name}】你大模型居然当众产生幻觉企图偷鸡！被我当场缴械合规纠正！"
            if not played_cards:
                return f"【{player_name}】摇了摇头表示'要唔起，过！'。眼神迷茫，估计手牌烂成一团。"
            if pattern_type in ["BOMB", "ROCKET"]:
                return f"💥 轰隆一声巨响！【{player_name}】直接甩出炸弹【{' '.join(played_cards)}】！牌局瞬间进入白热化！"
            if hand_remain == 1:
                return f"🚨【全场警报！】注意！【{player_name}】手上只剩最后【1 张牌】！进入绝杀赛点！"
            return f"【{player_name}】打出【{' '.join(played_cards)}】。看似漫不经心，其实暗藏杀机。"

        return self._call_live_ai(prompt, fallback)

    def victory_speech(self, winner_name, winner_role, landlord_name, players_state):
        """终局颁奖与颁发薯仔奖"""
        if winner_role == "地主":
            return (
                f"🎉【比赛结束！地主大获全胜！】\n"
                f"地主【{winner_name}】以一敌二成功杀出重围！两个农民配合得一塌糊涂！\n"
                f"🏆 恭喜【{winner_name}】夺冠！\n"
                f"🥔 裁判正式宣布：向两个农民联合颁发【终极大薯仔安慰奖】！"
            )
        else:
            return (
                f"🎉【比赛结束！农民翻身做主人！】\n"
                f"在农民【{winner_name}】的绝杀带领下，农民兄弟齐心合力推翻残酷统治！\n"
                f"地主【{landlord_name}】机关算尽，底牌再靓都救唔番盲目自信！\n"
                f"🏆 恭喜农民战队夺冠！地主请自觉领取【大番薯金像奖】！"
            )
