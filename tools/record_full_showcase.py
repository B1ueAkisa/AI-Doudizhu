"""
AI斗地主 · 赛博竞技场起源、全明星解说与43手完整实况 1080P 全自动声画录制流水线
流程：
1. 启动 1920x1080 无头 Chrome 广播画布
2. 访问 http://127.0.0.1:8888/video_showcase.html
   - Scene 0 片头介绍 (17.28s) 完整播讲
   - 自然触发跳转至 /replay.html?auto=1
3. Replay 完整牌桌实况
   - 第 1 至 43 手按序推进
   - 30 手关键回合播放粤语专属毒舌解说音频
   - 绝杀第 43 手完整播讲完毕后，展示胜者浮层 3.5s
   - 自动平滑跳转至 /video_showcase.html?scene=outro
4. 终幕致谢
   - 播放终幕解说音频 (24.89s) 与致谢卡
   - 播毕后触发 window.__presentationFinished = true
5. 音轨精准合成与封装
   - 根据前端控制台事件精确毫秒时间戳，使用 PCM 拼接生成 100% 同步的高清主音轨
   - 使用 ffmpeg 压制封装为 1080P 广播级 MP4
"""

import os
import sys
import time
import glob
import json
import subprocess
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VIDEO_DIR = os.path.join(BASE_DIR, 'videos')
AUDIO_DIR = os.path.join(VIDEO_DIR, 'audio')
TURNS_AUDIO_DIR = os.path.join(AUDIO_DIR, 'game2_turns')
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FINAL_MP4 = os.path.join(VIDEO_DIR, "AI斗地主_赛博全明星大赏_1080P声画同步版.mp4")

os.makedirs(VIDEO_DIR, exist_ok=True)

print("=" * 70, flush=True)
print("🚀 开始全流程 1080P 声画同步录制流水线", flush=True)
print(f"输出目标: {FINAL_MP4}", flush=True)
print("=" * 70, flush=True)

# 记录当前已有的 webm
existing_webms = set(glob.glob(os.path.join(VIDEO_DIR, "*.webm")))

audio_events = [] # [(clip_name, timestamp_ms)]
presentation_finished = False
rec_start_epoch = None

def get_mp3_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return float(json.loads(r.stdout)['format']['duration'])
    except Exception:
        return 5.0

def mp3_to_pcm(mp3_path, tempo=1.25):
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", mp3_path,
        "-filter:a", f"atempo={tempo}",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        "-"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return res.stdout

def create_silence(duration_sec):
    if duration_sec <= 0:
        return b''
    num_samples = int(duration_sec * 44100)
    return b'\x00' * (num_samples * 4)

t0 = time.time()

with sync_playwright() as p:
    print("\n[1/4] 正在启动 Chromium 1920x1080 广播录制引擎...", flush=True)
    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=[
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion",
        ]
    )
    context = browser.new_context(
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1920, "height": 1080},
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()

    def handle_console(msg):
        global presentation_finished
        txt = msg.text
        if "[AUDIO_EVENT] START:" in txt:
            # 格式: [AUDIO_EVENT] START:clipName:1740000000000
            try:
                raw = txt.split("START:")[1]
                parts = raw.split(":")
                clip = parts[0]
                ts = int(parts[1]) if len(parts) > 1 else int(time.time() * 1000)
                audio_events.append((clip, ts))
                print(f"  🎙️ [播音事件] {clip} (ts: {ts})", flush=True)
            except Exception as e:
                print(f"  ⚠️ 解析音频事件异常: {e}", flush=True)
        elif "SHOWCASE_PRESENTATION_FINISHED" in txt or "[RECORDING_FINISHED]" in txt:
            presentation_finished = True
            print("  🏁 [完成信号] 前端触发终幕致谢播毕信号！", flush=True)

    page.on("console", handle_console)
    page.on("pageerror", lambda err: print(f"  ⚠️ 页面错误: {err}", flush=True))

    start_url = "http://127.0.0.1:8888/video_showcase.html?speed=1.25"
    print(f"\n[2/4] 打开导播入口页面: {start_url}", flush=True)
    page.goto(start_url)
    try:
        rec_start_epoch = page.evaluate("() => window.__loadTime || Date.now()")
    except Exception:
        rec_start_epoch = int(time.time() * 1000)
    print(f"  🎬 视频基准时间戳校准完毕: {rec_start_epoch}", flush=True)

    # 循环监控等待播发完成，最长等待 500 秒 (8.3 分钟)
    max_wait_sec = 500
    step_check = 0
    while not presentation_finished and step_check < max_wait_sec:
        page.wait_for_timeout(1000)
        step_check += 1
        if step_check % 30 == 0:
            print(f"  ⏱️ 录制进行中... 已耗时 {step_check} 秒 (已记录 {len(audio_events)} 个语音片段)", flush=True)

    if presentation_finished:
        print(f"\n✅ 成功接收到终幕结束信号！总录制时长约 {step_check} 秒", flush=True)
    else:
        print(f"\n⚠️ 达到超时上限 {max_wait_sec} 秒，正在安全收尾...", flush=True)

    # 留 2.5 秒平滑淡出收尾
    page.wait_for_timeout(2500)
    print("正在封装原始视频流...", flush=True)
    page.close()
    context.close()
    browser.close()

# 找出本次生成的 webm
new_webms = set(glob.glob(os.path.join(VIDEO_DIR, "*.webm"))) - existing_webms
if not new_webms:
    all_webms = glob.glob(os.path.join(VIDEO_DIR, "*.webm"))
    all_webms.sort(key=os.path.getmtime, reverse=True)
    raw_webm = all_webms[0] if all_webms else None
else:
    cand = list(new_webms)
    cand.sort(key=os.path.getsize, reverse=True)
    raw_webm = cand[0]

if not raw_webm or not os.path.exists(raw_webm):
    print("❌ 未找到生成的原始 webm 视频！")
    sys.exit(1)

raw_video_dur = get_mp3_duration(raw_webm)
print(f"原始视频录制完成: {raw_webm}")
print(f"视频时长: {raw_video_dur:.2f} 秒, 大小: {round(os.path.getsize(raw_webm)/(1024*1024), 2)} MB")

print(f"\n[3/4] 正在根据实录时间戳构建精准同步母带音轨 (共 {len(audio_events)} 个语音节点)...", flush=True)

# 解析音频文件物理路径
resolved_clips = []
for clip_name, ts in audio_events:
    path = None
    if clip_name == "scene_intro_fast":
        path = os.path.join(AUDIO_DIR, "scene_intro_fast.mp3")
    elif clip_name in ["scene_outro_fast", "scene_outro"]:
        path = os.path.join(AUDIO_DIR, "scene_outro_fast.mp3")
    elif clip_name.startswith("turn_"):
        path = os.path.join(TURNS_AUDIO_DIR, f"{clip_name}.mp3")
    else:
        p = os.path.join(AUDIO_DIR, f"{clip_name}.mp3")
        if os.path.exists(p):
            path = p

    if path and os.path.exists(path):
        resolved_clips.append({
            'name': clip_name,
            'ts': ts,
            'path': path,
            'dur': get_mp3_duration(path)
        })
    else:
        print(f"  ⚠️ 未找到音频文件: {clip_name} ({path})")

print(f"有效音频节点: {len(resolved_clips)} 个")

# 计算各片段相对于视频起始帧的绝对时间偏移
if resolved_clips:
    base_ts = rec_start_epoch or resolved_clips[0]['ts']
    # 如果第一个音频时间戳早于 base_ts，以第一个音频为准
    if resolved_clips[0]['ts'] < base_ts:
        base_ts = resolved_clips[0]['ts']

    master_pcm = b''
    current_time_sec = 0.0

    for idx, c in enumerate(resolved_clips):
        start_sec = max(0.0, (c['ts'] - base_ts) / 1000.0)
        
        # 如果有静音间隙，插入静音
        if start_sec > current_time_sec:
            silence_len = start_sec - current_time_sec
            master_pcm += create_silence(silence_len)
            current_time_sec = start_sec
        elif start_sec < current_time_sec:
            # 极少数情况下有轻微交叉，平移到当前末尾
            start_sec = current_time_sec

        pcm_data = mp3_to_pcm(c['path'])
        master_pcm += pcm_data
        actual_dur = len(pcm_data) / (44100 * 4)
        current_time_sec += actual_dur

    # 末尾补足到视频长度
    if current_time_sec < raw_video_dur:
        master_pcm += create_silence(raw_video_dur - current_time_sec)

    soundtrack_m4a = os.path.join(VIDEO_DIR, "master_soundtrack.m4a")
    print(f"正在编码高清 AAC 母带音轨 ({len(master_pcm)/(44100*4):.2f}s)...", flush=True)
    enc_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "s16le",
        "-ar", "44100",
        "-ac", "2",
        "-i", "-",
        "-c:a", "aac",
        "-b:a", "192k",
        soundtrack_m4a
    ]
    enc_proc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    enc_proc.communicate(input=master_pcm)
    print(f"母带音轨生成完成: {soundtrack_m4a} ({round(os.path.getsize(soundtrack_m4a)/(1024*1024), 2)} MB)", flush=True)
else:
    print("❌ 未捕获到任何有效音频事件，无法混音！")
    sys.exit(1)

print(f"\n[4/4] 正在调用 ffmpeg 进行 1080P 广播级音画合成与 H.264 压制...", flush=True)
mux_cmd = [
    'ffmpeg', '-y',
    '-i', raw_webm,
    '-i', soundtrack_m4a,
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '19',
    '-c:a', 'copy',
    '-pix_fmt', 'yuv420p',
    '-shortest',
    FINAL_MP4
]

res = subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0 and os.path.exists(FINAL_MP4):
    final_size_mb = round(os.path.getsize(FINAL_MP4) / (1024 * 1024), 2)
    final_dur = get_mp3_duration(FINAL_MP4)
    total_elapsed = round(time.time() - t0, 1)
    print("\n" + "=" * 70, flush=True)
    print("🎉 1080P 声画同步赛事长视频录制并压制成功！", flush=True)
    print(f"📁 视频文件: {FINAL_MP4}", flush=True)
    print(f"⏱️ 视频时长: {final_dur:.1f} 秒 ({final_dur/60:.1f} 分钟)", flush=True)
    print(f"💾 文件大小: {final_size_mb} MB", flush=True)
    print(f"⌛ 总运行耗时: {total_elapsed} 秒", flush=True)
    print("=" * 70, flush=True)
else:
    print(f"❌ ffmpeg 压制失败: {res.stderr.decode('utf-8', errors='ignore')}")
    sys.exit(1)
