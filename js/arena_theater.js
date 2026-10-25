// 竞技场复盘剧场模块
    function openReplayTheater() {
      stopAutoPlay();
      window.open('/replay.html', '_blank');
    }

    function closeReplayTheater() {
      isReplayMode = false;
      stopReplayAuto();
      document.getElementById('replayBroadcastBar').style.display = 'none';
      document.getElementById('geminiCommentaryBox').style.display = 'none';
      document.getElementById('centerArena').style.display = 'flex';
      [0, 1, 2].forEach(i => {
        const b = document.getElementById(`bubble_${i}`);
        if (b) b.classList.remove('visible');
        const c = document.getElementById(`card_${i}`);
        if (c) c.classList.remove('active-turn');
      });
      if (currentState) {
        updateUI(currentState);
      }
    }

    function renderReplayStep(stepNum) {
      if (!replayTurns || !replayTurns.length) return;
      stepNum = Math.max(1, Math.min(stepNum, replayTurns.length));
      currentReplayIdx = stepNum - 1;
      const t = replayTurns[currentReplayIdx];

      document.getElementById('replayProgress').value = stepNum;
      document.getElementById('replayStepTag').innerText = `第 ${stepNum} / ${replayTurns.length} 手`;
      const playStr = t.actual_play && t.actual_play.length ? '打出【' + t.actual_play.join(' ') + '】' : '不出 (PASS)';
      document.getElementById('replayTurnTitle').innerText = `第 ${stepNum} 手：【${t.model_name}】(${t.role}) ${playStr}`;

      const seatIdx = t.seat.includes('底部') ? 0 : (t.seat.includes('右方') ? 1 : 2);

      // 席位卡高亮
      [0, 1, 2].forEach(i => {
        const c = document.getElementById(`card_${i}`);
        if (c) c.classList.toggle('active-turn', i === seatIdx);
      });

      // 气泡流式文本展示
      [0, 1, 2].forEach(i => {
        const b = document.getElementById(`bubble_${i}`);
        if (b) {
          if (i === seatIdx) {
            b.classList.add('visible');
            let rawThink = (t.raw_thinking || '').replace(/<think>|<\/think>/g, '').trim();
            if (rawThink.length > 85) rawThink = rawThink.slice(0, 85) + '...';
            b.innerText = rawThink || `思考中: 决定出【${playStr}】`;
          } else {
            b.classList.remove('visible');
          }
        }
      });

      // 手牌展示重构 (按该手当时的真实剩余手牌渲染)
      const handEl = document.getElementById(`hand_${seatIdx}`);
      if (handEl && t.hand_before) {
        if (seatIdx === 0) {
          handEl.innerHTML = t.hand_before.map((c, i) => renderCard(c, false, i + 1)).join('');
        } else {
          handEl.innerHTML = `<div style="display:flex; align-items:center;">${t.hand_before.map((c, i) => renderCard(c, true, i + 1)).join('')}</div>`;
        }
        document.getElementById(`count_${seatIdx}`).innerText = `手牌: ${t.hand_before.length} 张`;
      }

      // 台面牌放置与飞牌动效
      const zoneEl = document.getElementById(`played_zone_${seatIdx}`);
      if (zoneEl) {
        if (t.actual_play && t.actual_play.length) {
          zoneEl.style.display = 'flex';
          zoneEl.innerHTML = `
            <div class="played-zone-tag tag-seat-${seatIdx}">${t.model_name} 打出：</div>
            <div class="played-cards-row">${t.actual_play.map(c => renderCard(c, true)).join('')}</div>
          `;
          animateCardThrow(seatIdx, t.actual_play);
        } else {
          zoneEl.style.display = 'flex';
          zoneEl.innerHTML = `
            <div class="played-zone-tag tag-seat-${seatIdx}">${t.model_name}</div>
            <div class="pass-stamp">不出 (PASS)</div>
          `;
        }
      }

      // Gemini 毒舌解说词
      const commBox = document.getElementById('geminiCommentaryText');
      if (commBox) {
        commBox.innerHTML = t.gemini_commentary || `第 ${stepNum} 手：战况扑朔迷离，看选手们如何博弈！`;
      }

      // 如果开启自动解说，设定定时器推进
      if (isReplayAuto) {
        const speedMs = parseInt(document.getElementById('replaySpeedSel').value) || 3800;
        clearTimeout(replayTimer);
        if (stepNum < replayTurns.length) {
          replayTimer = setTimeout(() => {
            renderReplayStep(stepNum + 1);
          }, speedMs);
        } else {
          stopReplayAuto();
          if (commBox) {
            commBox.innerHTML = '🏆 42手史诗对决完整复盘结束！恭喜农民组合拿下胜利！';
          }
        }
      }
    }

    function toggleReplayAuto() {
      if (isReplayAuto) {
        stopReplayAuto();
      } else {
        startReplayAuto();
      }
    }

    function startReplayAuto() {
      if (currentReplayIdx >= replayTurns.length - 1) {
        currentReplayIdx = -1;
      }
      isReplayAuto = true;
      document.getElementById('btnReplayAuto').innerText = "⏸️ 暂停解说";
      renderReplayStep(currentReplayIdx + 2);
    }

    function stopReplayAuto() {
      isReplayAuto = false;
      clearTimeout(replayTimer);
      const btn = document.getElementById('btnReplayAuto');
      if (btn) btn.innerText = "▶️ 自动解说";
    }

    function nextReplayStep() {
      stopReplayAuto();
      renderReplayStep(currentReplayIdx + 2);
    }

    function prevReplayStep() {
      stopReplayAuto();
      renderReplayStep(currentReplayIdx);
    }

    function seekReplayStep(val) {
      stopReplayAuto();
      renderReplayStep(parseInt(val));
    }

    function restartReplay() {
      stopReplayAuto();
      renderReplayStep(1);
    }

    window.onload = async () => {
      await loadRoster();
      fetchState();
    };