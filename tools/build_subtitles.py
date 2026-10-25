# -*- coding: utf-8 -*-
"""
生成 1080P 广播级 AI 斗地主赛事解说字幕文件 (.srt 与 .vtt)
- 依据录制实录时间戳校准毫秒级起始时间
- 依据 1.25x 语速精确折算每段时长
- 智能句子切分，短句舒展，适合观众阅读与视频平台挂载
"""
import os
import re
import sys
import json
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"d:\AKFile\其他\AI斗地主"
AUDIO_DIR = os.path.join(BASE_DIR, "videos", "audio")
TURNS_DIR = os.path.join(AUDIO_DIR, "game2_turns")
LOG_PATH = r"C:\Users\Administrator\.gemini\antigravity\brain\a4daa634-e8d4-4e79-aabd-63c81ebb56fc\.system_generated\tasks\task-4828.log"

TEMPO = 1.25

# 1. 片头文稿
INTRO_SCRIPT = (
    "各位观众大家好！欢迎收睇《AI斗地主·赛博癫王全明星大竞技》！"
    "今次呢个斗地主竞技场，全程使用 Google 最新嘅 Anti-gravity 平台全自动开发，操刀写代码嘅主力核心模型一直都系我 Gemini！"
    "解说配音采用高保真粤语神经语音引擎；"
    "参赛选手包括智谱 GLM-4、自带深度思考链嘅 GLM-Z1 推理模型，同埋阿里 Qwen2.5；"
    "我哋仲拉埋特级大师 Gemini 3.1 Pro 一齐入局深度复盘！"
    "大模型打牌究竟有几癫？废话少讲，即刻进入 43 手神仙大逆转！"
)

# 2. 片尾文稿
OUTRO_SCRIPT = (
    "全场四十三手惊天惨案圆满收官！"
    "地主残局以红心六潇洒偷家夺冠，而农民手握绝对胜势，竟然违背报单原则惨痛送命！"
    "大模型打牌，真系由头到尾充满惊喜同笑料！"
    "多谢各位观众收睇！我系首席主控判官 Gemini 3.8 Flash，联同特邀特级大师 Gemini 3.1 Pro，我哋下期赛博竞技场再见！"
)

# 3. 对局各手精确解说词
TURNS_SCRIPTS = {
    1: "开局首发！地主 GLM-4 甩出四五六七八五连顺试探，虽剥离杂牌，却将七和六孤立成两张残局死穴！",
    2: "下家 Qwen 急躁冒进！掏出九、十、J、Q、K 强压，竟然强行拆毁一对 Q 和三张 J，开局就自废对子防线！",
    4: "地主思维链短路！企图用散牌越级压制顺子，被裁判规则引擎亮黄牌警告并强制 PASS！",
    5: "Qwen 自由领出发牌，打出一对五探路，寻求与上家 Z1 的对子呼应。",
    6: "Z1 犯下防守大忌！手握三张 K，竟然直接拆出一对 K 截杀对五！不仅跨度过大，更自废三张牌成套潜力！",
    7: "地主受迫交出顶层资源，打出唯一的对 A 强压对 K，防守牌提前见底。",
    8: "Qwen 暴脾气发作！面对对 A 竟然直接轰出一对二！第八手就将全队唯一的对二炸死，中盘彻底丧失控场权！",
    11: "Qwen 致命领牌脑抽！轰完对二之后，手中明明有小单张，竟然打出一张中单 J，直接喂牌畀地主！",
    12: "Z1 协同放水！队友放出单 J，Z1 手握 A、K、K、A、二竟然选择 PASS，坐视地主廉价上手！",
    13: "地主小王试水探雷，测试全场大王到底潜伏喺边个手里。",
    14: "Qwen 大王毫不手软直接砸死小王！连续交出对二与大王，农民核武库彻底打空！",
    17: "Qwen 耗尽大牌后只剩杂碎单张，交出单张三，农民控场正式宣告终结。",
    18: "Z1 过激顶大牌！面对单张三竟然直接跳出单张 A，浪费顶层防御资源，更送给地主上手机会！",
    19: "全场胜负大转折！地主抓住农民大牌全空的虚弱期，以单张二强夺发球权！反攻狂飙正式爆发！",
    20: "Qwen 认知严重失调！面对单张二，思维链竟然写出单 Q 可以压过地主的单张二，陷入逻辑幻觉！",
    21: "规则释疑！斗地主不分花色！地主红桃二控场，Z1 手中的方块二点数完全相同，绝无二压二可能！Z1 企图用单 A 压制被拦截，农民只能全员 PASS！",
    22: "牌理重大败笔！地主三张九带对十重磅轰出！手握最烂对三同中坚大对十，正规职业牌理必须带走垫底对三！地主白白浪费大对十，留低对三成为后患死穴！",
    25: "地主毫不喘息再甩对 Q！农民无人能挡，地主手牌暴跌至四张！全场拉响一级防空警报！",
    28: "恶果显现！由于头先冇带走对三，地主此时被迫赤膊裸出最烂的对三！将生死破绽拱手让畀农民！",
    30: "悬崖勒马！Z1 抓住地主对三的破绽，一对八精准截停，夺回万金不换的发球权，挽救第一赛点！",
    32: "Qwen 幻觉大爆发！面对 Z1 对八，思维链再次认定队友即将通关获胜，必须过牌护航，神游天外！",
    33: "Z1 顺子绝境反击！祭出三、四、五、六、七五连顺长套，强行将手牌缩减至七张！",
    35: "Qwen 阵营再陷幻觉！思维链再次宣称队友只剩两张即将获胜，彻底搞混地主同队友！",
    36: "送命领牌！明知地主只剩两张，Z1 竟然从容领出单张六，给地主精准送出脱手机会！",
    37: "地主笑纳大礼！甩出单张七压死单张六！手牌仅剩最后一张红心六！正式报单，决杀降临！",
    39: "特级大师级神级截杀！Z1 长考三十八秒，在悬崖边掏出方块二强行按死单张七！把地主封死在悬崖边！",
    40: "地主最后一张是单张六，被单张二结结实实按死在地上，动弹不得被迫 PASS！",
    41: "世纪大翻车！面对单张二，Qwen 思维链彻底短路，竟然以为报单的地主是队友，疯狂过牌保送！",
    42: "千古第一脑抽惨案！违背报单铁律！对手报单剩一张，控球方必须从大到小顶大单（必出单 A）！Z1 手握 A、K、J、十、四必胜手牌，出 A 必赢，竟然脑抽领出单张四喂畀地主！思维链写出四防地主大牌反制！真系赛博大孝子！",
    43: "地主红心六压死单张四奇迹绝杀！赢了之后思维链还在写出六方便下一步调整策略，笑翻全场！"
}

def get_mp3_dur(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(r.stdout)['format']['duration'])

def split_to_sentences(text):
    # 按照标点切分为自然阅读行
    # 保留感叹号、句号、分号作为切分点
    parts = re.split(r'([！!？?。；;])', text)
    sentences = []
    curr = ""
    for p in parts:
        curr += p
        if p in ['！', '!', '？', '?', '。', '；', ';']:
            if curr.strip():
                # 如果单句太长（超过 35 字），进一步按逗号分
                if len(curr.strip()) > 36 and ('，' in curr or ',' in curr):
                    subparts = re.split(r'([，,])', curr)
                    subcurr = ""
                    for sp in subparts:
                        subcurr += sp
                        if sp in ['，', ',']:
                            if subcurr.strip():
                                sentences.append(subcurr.strip())
                                subcurr = ""
                    if subcurr.strip():
                        sentences.append(subcurr.strip())
                else:
                    sentences.append(curr.strip())
            curr = ""
    if curr.strip():
        sentences.append(curr.strip())
    return sentences

def format_timestamp_srt(sec):
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        secs += 1
        ms -= 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

def format_timestamp_vtt(sec):
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        secs += 1
        ms -= 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"

def main():
    print("正在从录制日志读取精确时间戳...")
    log_text = open(LOG_PATH, encoding='utf-8', errors='ignore').read()
    base_match = re.search(r'视频基准时间戳校准完毕:\s*(\d+)', log_text)
    if not base_match:
        print("未找到基准时间戳！")
        return
    base_ts = int(base_match.group(1))

    events = re.findall(r'\[播音事件\]\s*([a-zA-Z0-9_]+)\s*\(ts:\s*(\d+)\)', log_text)
    print(f"解析到 {len(events)} 个语音事件...")

    subtitle_entries = [] # [(start_sec, end_sec, text)]

    for clip_name, ts_str in events:
        ts = int(ts_str)
        start_sec = max(0.0, (ts - base_ts) / 1000.0)

        # 确定对应音频文件与文本
        if clip_name == "scene_intro_fast":
            audio_path = os.path.join(AUDIO_DIR, "scene_intro_fast.mp3")
            script = INTRO_SCRIPT
        elif clip_name in ["scene_outro_fast", "scene_outro"]:
            audio_path = os.path.join(AUDIO_DIR, "scene_outro_fast.mp3")
            script = OUTRO_SCRIPT
        elif clip_name.startswith("turn_"):
            turn_num = int(clip_name.split("_")[1])
            audio_path = os.path.join(TURNS_DIR, f"{clip_name}.mp3")
            script = TURNS_SCRIPTS.get(turn_num, "")
        else:
            continue

        if not os.path.exists(audio_path) or not script:
            continue

        orig_dur = get_mp3_dur(audio_path)
        actual_dur = orig_dur / TEMPO

        # 切分为句子
        sentences = split_to_sentences(script)
        total_len = sum(len(s) for s in sentences) or 1

        curr_t = start_sec
        for s in sentences:
            s_dur = actual_dur * (len(s) / total_len)
            s_end = curr_t + s_dur
            subtitle_entries.append((curr_t, s_end, s))
            curr_t = s_end

    print(f"共生成 {len(subtitle_entries)} 条精准对位字幕轴！")

    # 1. 导出 SRT
    srt_path = os.path.join(BASE_DIR, "videos", "AI斗地主_赛博全明星大赏_1080P声画同步版.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, (s_start, s_end, s_txt) in enumerate(subtitle_entries, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_timestamp_srt(s_start)} --> {format_timestamp_srt(s_end)}\n")
            f.write(f"{s_txt}\n\n")
    print(f"✅ SRT 字幕文件已生成: {srt_path} ({os.path.getsize(srt_path)} 字节)")

    # 2. 导出 VTT
    vtt_path = os.path.join(BASE_DIR, "videos", "AI斗地主_赛博全明星大赏_1080P声画同步版.vtt")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for idx, (s_start, s_end, s_txt) in enumerate(subtitle_entries, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_timestamp_vtt(s_start)} --> {format_timestamp_vtt(s_end)}\n")
            f.write(f"{s_txt}\n\n")
    print(f"✅ VTT 字幕文件已生成: {vtt_path} ({os.path.getsize(vtt_path)} 字节)")

if __name__ == "__main__":
    main()
