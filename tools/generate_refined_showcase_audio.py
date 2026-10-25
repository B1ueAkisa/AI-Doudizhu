# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import subprocess

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
PROXY = "http://127.0.0.1:7890"

import edge_tts

audio_dir = r"d:\AKFile\其他\AI斗地主\videos\audio"
os.makedirs(audio_dir, exist_ok=True)
VOICE = "zh-HK-WanLungNeural"

intro_text = (
    "各位观众大家好！欢迎收睇《AI斗地主·赛博癫王全明星大竞技》！"
    "今次呢个斗地主竞技场，全程使用 Google 最新嘅 Anti-gravity 平台全自动开发，操刀写代码嘅主力核心模型一直都系我 Gemini！"
    "解说配音采用高保真粤语神经语音引擎；"
    "参赛选手包括智谱 GLM-4、自带深度思考链嘅 GLM-Z1 推理模型，同埋阿里 Qwen2.5；"
    "我哋仲拉埋特级大师 Gemini 3.1 Pro 一齐入局深度复盘！"
    "大模型打牌究竟有几癫？废话少讲，即刻进入 43 手神仙大逆转！"
)

outro_text = (
    "全场四十三手惊天惨案圆满收官！"
    "地主残局以红心六潇洒偷家夺冠，而农民手握绝对胜势，竟然违背报单原则惨痛送命！"
    "大模型打牌，真系由头到尾充满惊喜同笑料！"
    "多谢各位观众收睇！我系首席主控判官 Gemini 3.8 Flash，联同特邀特级大师 Gemini 3.1 Pro，我哋下期赛博竞技场再见！"
)

def get_dur(file_path):
    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return float(res.stdout.strip())

async def generate(text, filename):
    out_file = os.path.join(audio_dir, filename)
    print(f"[TTS] 正在生成 {filename} ({len(text)}字)...")
    for attempt in range(1, 4):
        try:
            comm = edge_tts.Communicate(text, VOICE, rate="+0%", proxy=PROXY)
            await comm.save(out_file)
            dur = get_dur(out_file)
            print(f" -> 成功生成 {out_file} ({dur:.2f}s, 毫秒: {int(dur*1000)})")
            return int(dur * 1000)
        except Exception as e:
            print(f" ⚠️ 第 {attempt} 次失败: {e}")
            await asyncio.sleep(1.5)
    return 0

async def main():
    intro_ms = await generate(intro_text, "scene_intro_fast.mp3")
    outro_ms = await generate(outro_text, "scene_outro_fast.mp3")
    print(f"\n[DONE] Intro: {intro_ms}ms, Outro: {outro_ms}ms")

if __name__ == "__main__":
    asyncio.run(main())
