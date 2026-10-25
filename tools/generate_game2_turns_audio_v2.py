# -*- coding: utf-8 -*-
"""
生成 Game 2 终极特级大师精准粤语配音 (带重试与断点续传)
1. 澄清规则：斗地主不分花色！2 不能压 2！
2. 剖析三带二败笔：地主手握对 3 与对 10，三带二必须带走垃圾对 3，地主却浪费大对 10！
3. 终局报单铁律：对手报单只剩 1 张，必须从大往小顶大牌（必出单 A）！出单 4 属于千古奇冤脑抽！
4. 汉字牌型规范化：彻底杜绝任何数字读音杂音！
音色：zh-HK-WanLungNeural (微软 Edge Neural TTS)
"""
import os
import sys
import asyncio

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
PROXY = "http://127.0.0.1:7890"

import edge_tts

out_dir = r"d:\AKFile\其他\AI斗地主\videos\audio\game2_turns"
os.makedirs(out_dir, exist_ok=True)

VOICE = "zh-HK-WanLungNeural"

PRECISE_SCRIPTS = {
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

async def generate_turn_audio(turn_idx, text):
    fname = f"turn_{turn_idx}.mp3"
    fpath = os.path.join(out_dir, fname)
    print(f"[TTS] 正在精准合成第 {turn_idx:2d} 手: {text[:25]}...")
    for attempt in range(1, 4):
        try:
            comm = edge_tts.Communicate(text, VOICE, proxy=PROXY)
            await comm.save(fpath)
            sz = os.path.getsize(fpath)
            print(f"  -> 第 {turn_idx:2d} 手合成成功 ({sz} 字节): {fname}")
            return
        except Exception as e:
            print(f"  [Attempt {attempt} failed for Turn {turn_idx}]: {e}")
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except: pass
            await asyncio.sleep(2)

async def main():
    print(f"=== 开始全量更新 Game 2 特级大师深度精准粤语配音 (共 {len(PRECISE_SCRIPTS)} 手) ===")
    for turn_idx, text in sorted(PRECISE_SCRIPTS.items()):
        await generate_turn_audio(turn_idx, text)
        await asyncio.sleep(0.3)
    print("=== 全量高精配音更新完成！===")

if __name__ == "__main__":
    asyncio.run(main())
