@echo off
chcp 65001 > nul
title AI 斗地主大乱斗 · 竞技场
cd /d %~dp0

echo ===================================================
echo 🃏 正在启动 AI 斗地主大乱斗 · 薯仔争霸赛...
echo 🎙️ 裁判长兼荷官：Gemini 3.8 Flash High
echo 🤖 参赛选手：智谱小清、硅基阿强、求索坤哥
echo ===================================================

start http://127.0.0.1:8888
python server.py

pause
