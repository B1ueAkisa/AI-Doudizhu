"""
无头单局斗地主竞技运行脚本
用于自动化批量运行对局，生成原生原始牌谱
"""
import sys
import os
import json
import time
import random

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 切换到项目根目录
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from game_manager import GameManager

def run_game(game_tag=""):
    print(f"=== 开始运行无头斗地主对局 {game_tag} ===", flush=True)
    gm = GameManager()
    
    # 随机打乱三位免费选手的座位顺序，让不同模型轮流做地主
    models = ["GLM-4-Flash", "GLM-Z1-Flash", "Qwen/Qwen2.5-7B-Instruct"]
    random.shuffle(models)
    gm.set_lineup(models)
    
    print(f"选手入座顺序: 席位0={models[0]}, 席位1={models[1]}, 席位2={models[2]}", flush=True)
    landlord_player = gm.state["players"][gm.state["landlord_idx"]]
    print(f"抽签地主: 【{landlord_player['name']}】({landlord_player['seat']})", flush=True)
    print(f"公开底牌: {' '.join(gm.state['bottom_cards'])}", flush=True)
    
    turn_count = 0
    start_time = time.time()
    
    while gm.state["status"] == "playing":
        turn_count += 1
        curr_p = gm.state["players"][gm.state["current_turn"]]
        curr_role = curr_p["role"]
        curr_name = curr_p["name"]
        
        # 执行一步
        t0 = time.time()
        client_state = gm.step()
        cost = round(time.time() - t0, 1)
        
        last_rec = gm.state["turns_record"][-1] if gm.state["turns_record"] else {}
        action_str = " ".join(last_rec.get("actual_play", [])) if last_rec.get("actual_play") else "不出(PASS)"
        is_legal_str = "✅合规" if last_rec.get("is_legal", True) else f"🚨违规({last_rec.get('illegal_reason', '')})"
        
        print(f"第 {turn_count:2d} 手 | {curr_name[:12]:12s} ({curr_role}) -> {action_str:10s} | {is_legal_str} | 耗时: {cost}s | 余牌: {last_rec.get('hand_remain', 0)}", flush=True)
        
        # 安全保护：如果超过 100 手直接打平防止死循环
        if turn_count >= 100:
            print("⚠️ 达到最大步数上限 100，强制平局结束！", flush=True)
            break
            
    total_time = round(time.time() - start_time, 1)
    winner_name = gm.state.get("winner", "无")
    winner_role = gm.state.get("winner_role", "平局")
    print(f"\n🎉 对局结束！胜者: 【{winner_name}】({winner_role})，总手序: {turn_count} 手，总耗时: {total_time} 秒", flush=True)
    
    # 获取刚导出的原始对局文件
    raw_dir = os.path.join(project_dir, 'records_raw')
    files = [os.path.join(raw_dir, f) for f in os.listdir(raw_dir) if f.endswith('.json')]
    files.sort(key=os.path.getmtime, reverse=True)
    latest_raw_file = files[0] if files else None
    
    result_summary = {
        "status": "success",
        "raw_file": latest_raw_file,
        "turns_count": turn_count,
        "winner": winner_name,
        "winner_role": winner_role,
        "landlord": landlord_player['name'],
        "total_time": total_time,
        "lineup": models
    }
    
    print("\n[RESULT_JSON_START]", flush=True)
    print(json.dumps(result_summary, ensure_ascii=False, indent=2), flush=True)
    print("[RESULT_JSON_END]", flush=True)
    return result_summary

if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "AutoMatch"
    run_game(tag)
