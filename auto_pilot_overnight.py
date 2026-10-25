"""
AI 斗地主通宵全自动巡航与复盘流水线
- 纯免费模型（GLM-4-Flash, GLM-Z1-Flash, Qwen2.5-7B）随机轮替入座与地主抽签
- 无头自动公证竞技推进对局
- 自动生成双解说员牌谱（Gemini 3.8 Flash 首席毒舌判官 + Gemini Pro 职业特级大师）
- 自动归档至 records_commented 并热更新复盘室
"""
import os
import sys
import json
import time
import random

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
project_dir = os.path.abspath(os.path.dirname(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from game_manager import GameManager

def run_headless_match(match_index=1):
    print(f"\n==========================================", flush=True)
    print(f"🎴 开始自动推进第 {match_index} 局斗地主竞技...", flush=True)
    print(f"==========================================", flush=True)
    
    gm = GameManager()
    roster = ["GLM-4-Flash", "GLM-Z1-Flash", "Qwen/Qwen2.5-7B-Instruct"]
    random.shuffle(roster)
    gm.set_lineup(roster)
    
    landlord_p = gm.state["players"][gm.state["landlord_idx"]]
    print(f"入座阵容: 席位0={roster[0]}, 席位1={roster[1]}, 席位2={roster[2]}", flush=True)
    print(f"抽签地主: 【{landlord_p['name']}】({landlord_p['seat']})，公开底牌: {' '.join(gm.state['bottom_cards'])}", flush=True)
    
    turn = 0
    t_start = time.time()
    while gm.state["status"] == "playing":
        turn += 1
        curr = gm.state["players"][gm.state["current_turn"]]
        t0 = time.time()
        client_state = gm.step()
        cost = round(time.time() - t0, 1)
        
        last_rec = gm.state["turns_record"][-1] if gm.state["turns_record"] else {}
        action = " ".join(last_rec.get("actual_play", [])) if last_rec.get("actual_play") else "不出(PASS)"
        legal = "✅" if last_rec.get("is_legal", True) else f"🚨({last_rec.get('illegal_reason', '')})"
        print(f"第 {turn:2d} 手 | {curr['name'][:12]:12s} ({curr['role']}) -> {action:12s} | {legal} | 余牌: {last_rec.get('hand_remain', 0)} ({cost}s)", flush=True)
        if turn >= 100:
            print("⚠️ 达到最大步数 100，平局强制结束", flush=True)
            break
            
    total_time = round(time.time() - t_start, 1)
    winner = gm.state.get("winner", "无")
    winner_role = gm.state.get("winner_role", "平局")
    print(f"\n🎉 第 {match_index} 局完赛！胜者: 【{winner}】({winner_role})，总手序: {turn} 手，耗时: {total_time} 秒", flush=True)
    return turn, winner, winner_role

def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(f"🚀 AI 斗地主通宵自动巡航已启动！计划运行 {rounds} 局...", flush=True)
    for i in range(1, rounds + 1):
        run_headless_match(i)
        time.sleep(3)
    print(f"\n✨ 全部 {rounds} 局巡航已圆满完成！", flush=True)

if __name__ == "__main__":
    main()
