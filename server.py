"""
AI 斗地主竞技场 - Web 后端服务
提供可视化前端网页及控制 API，支持真机握手开场白、选手自由选配与多牌谱库（原始/精选解说）管理。
"""
import os
import sys
import json
import time
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from game_manager import GameManager, RECORD_PATH
from ai_players import FREE_MODEL_ROSTER, check_model_handshake

sys.stdout.reconfigure(encoding='utf-8')

gm = GameManager()

BASE_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE_DIR, 'records_raw')
COMMENTED_DIR = os.path.join(BASE_DIR, 'records_commented')
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(COMMENTED_DIR, exist_ok=True)

def scan_record_dir(folder, record_type):
    if not os.path.exists(folder):
        return []
    records = []
    file_list = [f for f in os.listdir(folder) if f.endswith('.json')]
    file_list.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)), reverse=True)
    for f in file_list:
        file_path = os.path.join(folder, f)
        try:
            mtime = os.path.getmtime(file_path)
            time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            size_kb = round(os.path.getsize(file_path) / 1024, 1)
            with open(file_path, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
            turns = data.get('turns_record') or data.get('turns') or []
            records.append({
                "filename": f,
                "type": record_type,
                "title": f.replace('.json', ''),
                "date": time_str,
                "turns_count": len(turns),
                "winner": data.get("winner", "未知"),
                "winner_role": data.get("winner_role", ""),
                "landlord": data.get("landlord", ""),
                "size_kb": size_kb,
                "has_turn_audio": bool(data.get("has_turn_audio", False) or ('43手' in f))
            })
        except Exception as e:
            records.append({
                "filename": f,
                "type": record_type,
                "title": f.replace('.json', ''),
                "date": "未知",
                "turns_count": 0,
                "size_kb": 0,
                "error": str(e)
            })
    return records

class ArenaHTTPHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path in ['/', '/index.html']:
            html_path = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(html_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(html_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "index.html not found")
        elif parsed.path in ['/replay', '/replay.html']:
            replay_path = os.path.join(BASE_DIR, 'replay.html')
            if os.path.exists(replay_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(replay_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "replay.html not found")
        elif parsed.path == '/api/state':
            state = gm.get_client_state()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/roster':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(FREE_MODEL_ROSTER, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/stream_step':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()
            try:
                for chunk in gm.stream_step():
                    self.wfile.write(chunk.encode('utf-8'))
                    self.wfile.flush()
            except Exception as e:
                import traceback
                print(f"[SSE stream_step Exception]: {e}")
                traceback.print_exc()
                try:
                    err_chunk = f"data: {json.dumps({'event': 'net_error', 'reason': f'服务器内部错误: {e}'})}\n\n"
                    self.wfile.write(err_chunk.encode('utf-8'))
                    self.wfile.flush()
                except:
                    pass
        elif parsed.path == '/api/records_list':
            # 返回精选已解说牌谱库与原始对局谱库
            commented_list = scan_record_dir(COMMENTED_DIR, 'commented')
            raw_list = scan_record_dir(RAW_DIR, 'raw')
            res = {
                "commented": commented_list,
                "raw": raw_list
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/load_record':
            # 动态载入指定牌谱 (防目录穿越)
            rec_type = qs.get('type', ['commented'])[0]
            filename = os.path.basename(qs.get('filename', [''])[0])
            target_file = None
            if filename:
                folder = COMMENTED_DIR if rec_type == 'commented' else RAW_DIR
                cand = os.path.join(folder, filename)
                if os.path.exists(cand):
                    target_file = cand

            if not target_file or not os.path.exists(target_file):
                target_file = RECORD_PATH

            if os.path.exists(target_file):
                with open(target_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "牌谱文件未找到"}, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/replay_record':
            # 优先载入最新的精选已解说牌谱！
            commented_list = scan_record_dir(COMMENTED_DIR, 'commented')
            target_path = None
            if commented_list:
                target_path = os.path.join(COMMENTED_DIR, commented_list[0]['filename'])
            elif os.path.exists(RECORD_PATH):
                target_path = RECORD_PATH

            if target_path and os.path.exists(target_path):
                with open(target_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"msg": "暂无完整对局记录"}, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/export_record':
            if not os.path.exists(RECORD_PATH):
                gm.export_record_to_file()
            if os.path.exists(RECORD_PATH):
                with open(RECORD_PATH, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"msg": "暂无完整对局记录，请先打完一局"}, ensure_ascii=False).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body_str = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            req_data = json.loads(body_str) if body_str else {}
        except:
            req_data = {}

        if parsed.path == '/api/new_game':
            state = gm.reset_game()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/step':
            state = gm.step()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/handshake_single':
            model_key = req_data.get('model', '')
            seat_idx = req_data.get('seat_idx', 0)
            res = check_model_handshake(model_key)
            res["model"] = model_key
            res["seat_idx"] = seat_idx
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/handshake':
            models = req_data.get('models', [])
            results = []
            for m in models:
                res = check_model_handshake(m)
                res["model"] = m
                results.append(res)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"results": results}, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/set_lineup':
            models = req_data.get('models', [])
            state = gm.set_lineup(models)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/save_commented_record':
            # 保存带解说的牌谱到 records_commented
            filename = os.path.basename(req_data.get('filename', f"commented_{int(time.time())}.json"))
            if not filename.endswith('.json'):
                filename += '.json'
            payload = req_data.get('data', {})
            save_path = os.path.join(COMMENTED_DIR, filename)
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "filename": filename}, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404, "API not found")

def run_server(port=8888):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, ArenaHTTPHandler)
    print(f"🃏 AI 斗地主竞技场已在 http://127.0.0.1:{port} 运行")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

if __name__ == '__main__':
    run_server(8888)
