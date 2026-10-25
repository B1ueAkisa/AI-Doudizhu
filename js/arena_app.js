let isAutoPlaying = false;
    let autoTimer = null;
    let countdownSec = 15;
    let countdownInterval = null;
    let roster = {};
    let currentState = null;


    async function fetchState() {
      try {
        const res = await fetch('/api/state');
        const state = await res.json();
        updateUI(state);
      } catch (err) {
        console.error(err);
      }
    }

    let liveTimerInterval = null;
    let turnStartTime = 0;

    function startThinkingClock(seatIdx) {
      clearInterval(liveTimerInterval);
      turnStartTime = Date.now();
      [0, 1, 2].forEach(i => {
        const tEl = document.getElementById(`timer_${i}`);
        if (i === seatIdx) {
          tEl.style.display = 'flex';
          tEl.className = 'countdown-timer';
          tEl.innerText = `⏱️ 思考中: 0s`;
        } else {
          tEl.style.display = 'none';
        }
      });

      liveTimerInterval = setInterval(() => {
        const elapsedSec = Math.floor((Date.now() - turnStartTime) / 1000);
        const activeTimer = document.getElementById(`timer_${seatIdx}`);
        if (activeTimer) {
          if (elapsedSec >= 135) {
            activeTimer.className = 'countdown-timer urgent';
            activeTimer.innerText = `⚠️ 思考即将超时: ${elapsedSec}s (上限150s)`;
          } else {
            activeTimer.className = 'countdown-timer';
            activeTimer.innerText = `⏱️ 思考中: ${elapsedSec}s (上限150s)`;
          }
        }
      }, 1000);
    }

    function updateThinkingClockActivity(seatIdx, elapsedFromServer) {
      const activeTimer = document.getElementById(`timer_${seatIdx}`);
      if (activeTimer) {
        const sec = Math.round(elapsedFromServer || (Date.now() - turnStartTime) / 1000);
        if (sec >= 50) {
          activeTimer.className = 'countdown-timer urgent';
          activeTimer.innerText = `⚠️ 正在推演: ${sec}s`;
        } else {
          activeTimer.className = 'countdown-timer';
          activeTimer.innerText = `🟢 正在推演: ${sec}s`;
        }
      }
    }

    function stopThinkingClock(seatIdx, durationSec) {
      clearInterval(liveTimerInterval);
      const activeTimer = document.getElementById(`timer_${seatIdx}`);
      if (activeTimer) {
        activeTimer.className = 'countdown-timer';
        const costStr = durationSec ? `${durationSec}s` : `${((Date.now() - turnStartTime) / 1000).toFixed(1)}s`;
        activeTimer.innerText = `✅ 本手耗时: ${costStr}`;
        setTimeout(() => {
          activeTimer.style.display = 'none';
        }, 2800);
      }
    }

    function updateUI(state, triggerAnimFor = -1, playedCards = null) {
      currentState = state;
      document.getElementById('roundCounter').innerText = `第 ${state.game_id} 局`;

      // 顶部阵容显示
      if (state.players && state.players.length >= 3) {
        document.getElementById('headerModel0').innerText = state.players[0].name;
        document.getElementById('headerModel1').innerText = state.players[1].name;
        document.getElementById('headerModel2').innerText = state.players[2].name;
      }

      // 1. 底牌
      const bottomCardsEl = document.getElementById('bottomCardsContainer');
      if (state.bottom_cards && state.bottom_cards.length) {
        bottomCardsEl.innerHTML = state.bottom_cards.map(c => renderCard(c, true)).join('');
      }

      // 2. 玩家渲染
      state.players.forEach((p, idx) => {
        const cardEl = document.getElementById(`card_${idx}`);
        const badgeEl = document.getElementById(`badge_${idx}`);
        const countEl = document.getElementById(`count_${idx}`);
        const nameEl = document.getElementById(`name_${idx}`);
        const avatarEl = document.getElementById(`avatar_${idx}`);
        const handEl = document.getElementById(`hand_${idx}`);
        const bubbleEl = document.getElementById(`bubble_${idx}`);

        nameEl.innerText = p.name;
        avatarEl.src = p.avatar;

        if (state.status === 'playing' && state.current_turn === idx) {
          cardEl.classList.add('active-turn');
        } else {
          cardEl.classList.remove('active-turn');
          bubbleEl.classList.remove('visible');
        }

        badgeEl.className = `role-badge ${p.role === '地主' ? 'role-landlord' : 'role-peasant'}`;
        badgeEl.innerText = p.role === '地主' ? '👑 大地主' : '🛡️ 农民';
        cardEl.classList.toggle('is-landlord', p.role === '地主');
        cardEl.classList.toggle('is-peasant', p.role !== '地主');
        countEl.innerText = `手牌: ${p.hand.length} 张`;

        if (p.hand && p.hand.length) {
          if (idx === 0) {
            handEl.innerHTML = p.hand.map((c, i) => renderCard(c, false, i + 1)).join('');
          } else {
            if (p.hand.length > 8) {
              const r1 = p.hand.slice(0, Math.ceil(p.hand.length / 2));
              const r2 = p.hand.slice(Math.ceil(p.hand.length / 2));
              handEl.innerHTML = `
                <div style="display:flex; align-items:center;">
                  ${r1.map((c, i) => renderCard(c, true, i + 1)).join('')}
                </div>
                <div style="display:flex; align-items:center; margin-top:-6px;">
                  ${r2.map((c, i) => renderCard(c, true, i + 1)).join('')}
                </div>
              `;
            } else {
              handEl.innerHTML = `<div style="display:flex; align-items:center;">${p.hand.map((c, i) => renderCard(c, true, i + 1)).join('')}</div>`;
            }
          }
        } else {
          handEl.innerHTML = '<span style="color:#4cd137;font-weight:900;font-size:18px;">手牌已出完！</span>';
        }
      });

      // 3. 倒计时时钟清理 (仅在对局结束或非出牌态时重置)
      if (state.status !== 'playing') {
        clearInterval(liveTimerInterval);
        [0, 1, 2].forEach(i => document.getElementById(`timer_${i}`).style.display = 'none');
      }

      // 4. 三家专属台面出牌区 (每位选手面前放置，新一轮自动清空)
      [0, 1, 2].forEach(idx => {
        const zoneEl = document.getElementById(`played_zone_${idx}`);
        if (!zoneEl) return;
        const p = state.players[idx];
        const pName = p ? p.name : `选手 ${idx}`;
        const trickInfo = (state.trick_played && state.trick_played[String(idx)]) || null;

        if (!trickInfo) {
          zoneEl.style.display = 'none';
          zoneEl.innerHTML = '';
        } else if (trickInfo.action === '不出') {
          zoneEl.style.display = 'flex';
          zoneEl.innerHTML = `
            <div class="played-zone-tag tag-seat-${idx}">${pName}</div>
            <div class="pass-stamp">不出 (PASS)</div>
          `;
        } else if (trickInfo.cards && trickInfo.cards.length) {
          zoneEl.style.display = 'flex';
          zoneEl.innerHTML = `
            <div class="played-zone-tag tag-seat-${idx}">${pName} 打出：</div>
            <div class="played-cards-row">
              ${trickInfo.cards.map(c => renderCard(c, true)).join('')}
            </div>
          `;
        } else {
          zoneEl.style.display = 'none';
          zoneEl.innerHTML = '';
        }
      });

      // 5. 中央牌权领出指示
      const centerLabel = document.getElementById('centerActionLabel');
      const centerCards = document.getElementById('centerCards');
      if (state.last_valid_play && state.last_valid_play.length) {
        centerLabel.innerText = `当前最大：【${state.last_valid_player_name}】打出`;
        centerCards.innerHTML = state.last_valid_play.map(c => renderCard(c, true)).join('');
      } else {
        const curr = state.players[state.current_turn];
        centerLabel.innerText = `等待【${curr ? curr.name : ''}】自由开局出牌`;
        centerCards.innerHTML = `<span style="color:#95afc0;font-size:14px;">牌权在手，随意出牌</span>`;
      }

      // 6. 飞牌动效与气泡自然淡出
      if (triggerAnimFor >= 0 && playedCards && playedCards.length) {
        animateCardThrow(triggerAnimFor, playedCards);
        // 出完牌后，该选手头顶气泡慢慢淡出
        const justPlayedBubble = document.getElementById(`bubble_${triggerAnimFor}`);
        if (justPlayedBubble) {
          setTimeout(() => {
            justPlayedBubble.classList.remove('visible');
          }, 1000);
        }
      }

      // 炸弹特效
      if (state.last_action_type === 'BOMB' || state.last_action_type === 'ROCKET') {
        triggerBombEffect();
      }

      // 7. 右侧流式思维链日志栏 (已结束轮次默认自动折叠，保持整洁)
      if (triggerAnimFor < 0) {
        const streamEl = document.getElementById('logStream');
        let html = '';
        state.turns_record.forEach((turn, tIdx) => {
          const seatClass = `seat-${turn.seat.includes('底部') ? 0 : (turn.seat.includes('右方') ? 1 : 2)}`;
          const verdictHtml = turn.is_legal
            ? `<span class="verdict-tag verdict-pass">✅ 合规放行</span>`
            : `<span class="verdict-tag verdict-block">❌ 拦截: ${turn.illegal_reason}</span>`;
          const rawLen = (turn.raw_thinking || '').length;

          html += `
            <div class="stream-card ${seatClass}">
              <div class="stream-card-header">
                <span><b>${turn.model_name}</b> (${turn.role} · ${turn.seat.split(' ')[0]})</span>
                <span>第 ${turn.turn_index} 手 ${verdictHtml}</span>
              </div>
              <div style="font-size:12px;color:var(--gold-bright);margin-bottom:4px;font-weight:bold;">
                👉 动作: ${turn.actual_play.length ? '打出【' + turn.actual_play.join(' ') + '】' : '不出 (PASS)'}
              </div>
              <button class="cot-toggle-btn" onclick="toggleCot(this)">🔽 展开查看完整思维链 (${rawLen} 字)</button>
              <div class="live-cot-text" style="display:none;white-space:pre-wrap;font-size:12px;color:#dcdde1;line-height:1.5;max-height:300px;overflow-y:auto;background:rgba(0,0,0,0.3);padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);margin-top:6px;">${turn.raw_thinking || '无思维链'}</div>
            </div>
          `;
        });
        streamEl.innerHTML = html;
        streamEl.scrollTop = streamEl.scrollHeight;
      }

      // 8. 结算弹窗
      if (state.status === 'game_over') {
        stopAutoPlay();
        document.getElementById('modalTitle').innerText = `🏆 【${state.winner}】率先出完所有手牌！`;
        document.getElementById('modalText').innerText = `胜负已分！获胜方：【${state.winner_role}】（${state.winner}）。本局全部真实思维链已保存到本地，可立即呼叫 Gemini 展开战术复盘！`;
        document.getElementById('victoryModal').style.display = 'flex';
      } else {
        document.getElementById('victoryModal').style.display = 'none';
      }
    }

    async function startNewGame() {
      stopAutoPlay();
      isStepRunning = false;
      document.getElementById('btnNextStep').disabled = true;
      try {
        const res = await fetch('/api/new_game', { method: 'POST' });
        const state = await res.json();
        [0, 1, 2].forEach(i => {
          const b = document.getElementById(`bubble_${i}`);
          if (b) {
            b.classList.remove('visible');
            b.innerText = '';
          }
          const t = document.getElementById(`timer_${i}`);
          if (t) t.style.display = 'none';
          const c = document.getElementById(`card_${i}`);
          if (c) c.classList.remove('active-turn');
          const pz = document.getElementById(`played_zone_${i}`);
          if (pz) {
            pz.style.display = 'none';
            pz.innerHTML = '';
          }
        });
        clearInterval(liveTimerInterval);
        document.getElementById('logStream').innerHTML = '';
        updateUI(state);
      } catch (err) {
        console.error(err);
      } finally {
        isStepRunning = false;
        document.getElementById('btnNextStep').disabled = false;
      }
    }

    let isStepRunning = false;

    async function stepTurn() {
      if (isStepRunning) return;
      isStepRunning = true;
      document.getElementById('btnNextStep').disabled = true;

      let finalStatus = 'playing';
      // 0ms 零延迟立即定位当前出手席位
      let activeSeat = (currentState && currentState.current_turn !== undefined) ? currentState.current_turn : 0;
      let activeStreamCard = null;
      let cotBodyEl = null;
      let actionDescEl = null;
      let statusPillEl = null;
      let fullCotText = '';

      const player = (currentState && currentState.players) ? currentState.players[activeSeat] : null;
      const modelDisplayName = player ? player.name : 'AI 选手';

      // 1. 头顶气泡立刻弹起！说明本地程序正常发出请求
      const bubble = document.getElementById(`bubble_${activeSeat}`);
      if (bubble) {
        bubble.innerText = `📡 [本地请求已发出] 正在连线【${modelDisplayName}】，等待云端响应...`;
        bubble.classList.add('visible');
      }

      // 2. 玩家卡片立刻亮起，时钟起跑
      [0, 1, 2].forEach(i => {
        const c = document.getElementById(`card_${i}`);
        if (c) {
          if (i === activeSeat) c.classList.add('active-turn');
          else c.classList.remove('active-turn');
        }
      });
      startThinkingClock(activeSeat);

      // 3. 右侧日志栏立即插入占位状态卡片
      const streamEl = document.getElementById('logStream');
      activeStreamCard = document.createElement('div');
      activeStreamCard.className = `stream-card seat-${activeSeat}`;
      activeStreamCard.innerHTML = `
        <div class="stream-card-header">
          <span><b>${modelDisplayName}</b> (${player ? player.role : ''})</span>
          <span class="status-pending" style="font-size:11.5px;padding:2px 8px;border-radius:10px;background:#0984e3;color:#fff;">📡 正在呼叫云端 API...</span>
        </div>
        <div class="live-action-line" style="font-size:12px;color:var(--gold-bright);margin-bottom:6px;font-weight:bold;">
          👉 [本地程序运行正常] 已向云端发出请求，等待对面大模型首字返回...
        </div>
        <div class="live-cot-text" style="white-space:pre-wrap;font-size:12.5px;color:#dcdde1;line-height:1.5;max-height:300px;overflow-y:auto;background:rgba(0,0,0,0.3);padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);">
          <span style="color:#74b9ff;font-style:italic;">[系统监控] 本地程序已向大模型平台发起流式请求，计时已启动。若对面服务器拥堵，裁判将在时限到达时自动接管，请耐心等待...</span>
        </div>
      `;
      streamEl.appendChild(activeStreamCard);
      cotBodyEl = activeStreamCard.querySelector('.live-cot-text');
      actionDescEl = activeStreamCard.querySelector('.live-action-line');
      statusPillEl = activeStreamCard.querySelector('.stream-card-header span:last-child');
      streamEl.scrollTop = streamEl.scrollHeight;

      const abortCtrl = new AbortController();
      const abortTimer = setTimeout(() => abortCtrl.abort(), 165000);

      try {
        const response = await fetch('/api/stream_step', { signal: abortCtrl.signal });
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let isFinished = false;

        while (!isFinished) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop();

          for (const part of parts) {
            const line = part.trim();
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.event === 'start') {
                  activeSeat = data.seat_idx;
                  if (data.is_free_turn) {
                    [0, 1, 2].forEach(i => {
                      const z = document.getElementById(`played_zone_${i}`);
                      if (z) { z.style.display = 'none'; z.innerHTML = ''; }
                    });
                    const cCards = document.getElementById('centerCards');
                    if (cCards) cCards.innerHTML = '<span style="color:#95afc0;font-size:14px;">新一轮开始，等待自由出牌...</span>';
                  }
                } else if (data.event === 'connecting') {
                  if (actionDescEl) {
                    actionDescEl.innerText = '👉 ' + data.msg;
                  }
                  if (bubble) {
                    bubble.innerText = '🌐【HTTP已连通】等待【' + data.model_name + '】返回首字...';
                  }
                } else if (data.event === 'first_token') {
                  if (statusPillEl) {
                    statusPillEl.style.background = '#2ed573';
                    statusPillEl.innerText = '🟢 对面模型已响应 (' + data.latency + 's)！正在推演...';
                  }
                  if (actionDescEl) {
                    actionDescEl.innerText = '👉 对面大模型正在全速流式输出思维链...';
                  }
                  if (bubble) {
                    bubble.innerText = '🟢【大模型已响应】正在输出思维链...';
                  }
                  if (cotBodyEl) {
                    cotBodyEl.innerText = '';
                  }
                } else if (data.event === 'token' || data.event === 'rethink_token') {
                  fullCotText += data.chunk;
                  updateThinkingClockActivity(activeSeat, data.elapsed);
                  if (cotBodyEl) {
                    cotBodyEl.innerText = fullCotText;
                    cotBodyEl.scrollTop = cotBodyEl.scrollHeight;
                  }
                  if (bubble) {
                    let bubbleDisplay = fullCotText.replace(/<think>/g, '').replace(/<\/think>/g, '').trim();
                    if (bubbleDisplay.length > 90) {
                      bubbleDisplay = '...' + bubbleDisplay.slice(-90);
                    }
                    bubble.innerText = bubbleDisplay || "🧠 分析中...";
                  }
                  if (streamEl) streamEl.scrollTop = streamEl.scrollHeight;
                } else if (data.event === 'retry_429') {
                  if (statusPillEl) {
                    statusPillEl.style.background = '#e67e22';
                    statusPillEl.innerText = `⚠️ 429限频重试 (${data.attempt}/${data.max})`;
                  }
                  if (actionDescEl) {
                    actionDescEl.innerText = `👉 [网络限频提示] ${data.msg}`;
                  }
                  if (bubble) {
                    bubble.innerText = `⚠️【云端429限频】重试中 (${data.attempt}/${data.max})，等待 ${data.wait}s...`;
                  }
                  if (cotBodyEl) {
                    const retryDiv = document.createElement('div');
                    retryDiv.style.cssText = "margin:6px 0;padding:4px 8px;background:rgba(230,126,34,0.25);border-left:3px solid #e67e22;border-radius:4px;color:#f39c12;font-size:11.5px;";
                    retryDiv.innerText = `⚠️ [429 限频重试 ${data.attempt}/${data.max}]: 遇到云端频率限制，等待 ${data.wait}s 后自动重试...`;
                    cotBodyEl.appendChild(retryDiv);
                  }
                  if (streamEl) streamEl.scrollTop = streamEl.scrollHeight;
                } else if (data.event === 'timeout' || data.event === 'net_error') {
                  if (statusPillEl) {
                    statusPillEl.style.background = '#e84118';
                    statusPillEl.innerText = '⏱️ 对面超时，裁判强制接管！';
                  }
                  if (actionDescEl) {
                    actionDescEl.innerText = '🚨 ' + data.reason;
                  }
                  if (cotBodyEl) {
                    const timeoutDiv = document.createElement('div');
                    timeoutDiv.style.cssText = "margin:8px 0;padding:6px 10px;background:rgba(235,47,6,0.3);border-left:4px solid #eb2f06;border-radius:4px;color:#ff7675;font-size:12px;font-weight:bold;";
                    timeoutDiv.innerHTML = `⏱️ ${data.reason}`;
                    cotBodyEl.appendChild(timeoutDiv);
                  }
                  if (bubble) {
                    bubble.innerText = `⏱️ 对面模型超时/无响应，裁判强制代选！`;
                  }
                  if (streamEl) streamEl.scrollTop = streamEl.scrollHeight;
                } else if (data.event === 'rejected') {
                  if (cotBodyEl) {
                    const alertDiv = document.createElement('div');
                    alertDiv.style.cssText = "margin:8px 0;padding:6px 10px;background:rgba(235,47,6,0.3);border-left:4px solid #eb2f06;border-radius:4px;color:#ff7675;font-size:12px;font-weight:bold;";
                    alertDiv.innerHTML = `🚨 裁判违规拦截：${data.reason}<br>⚠️ 勒令反思真实手牌重新出牌！`;
                    cotBodyEl.appendChild(alertDiv);
                  }
                  if (bubble) {
                    bubble.innerText = `🚨【裁判拦截】${data.reason}！重新思考中...`;
                  }
                  if (streamEl) streamEl.scrollTop = streamEl.scrollHeight;
                } else if (data.event === 'finish') {
                  clearTimeout(abortTimer);
                  finalStatus = data.state.status;
                  stopThinkingClock(activeSeat, data.duration);
                  
                  if (statusPillEl) {
                    statusPillEl.className = data.is_legal ? 'verdict-tag verdict-pass' : 'verdict-tag verdict-block';
                    statusPillEl.innerHTML = `${data.is_legal ? '✅ 合规放行' : '❌ 裁判强制执行'} <span style="font-size:11px;color:#f5f6fa;margin-left:4px;">(${data.duration || ''}s)</span>`;
                  }
                  if (actionDescEl) {
                    actionDescEl.innerText = `👉 动作: ${data.actual_play && data.actual_play.length ? '打出【' + data.actual_play.join(' ') + '】' : '不出 (PASS)'}`;
                  }

                  // 思考结束：自动折叠长篇思维链，附上展开/收起按钮
                  if (cotBodyEl) {
                    cotBodyEl.style.display = 'none';
                    const cotLen = fullCotText.length;
                    const toggleBtn = document.createElement('button');
                    toggleBtn.className = 'cot-toggle-btn';
                    toggleBtn.innerHTML = `🔽 展开查看完整思维链 (${cotLen} 字)`;
                    toggleBtn.onclick = function() { toggleCot(this); };
                    if (actionDescEl) {
                      actionDescEl.after(toggleBtn);
                    } else {
                      activeStreamCard.appendChild(toggleBtn);
                    }
                  }

                  updateUI(data.state, activeSeat, data.actual_play);

                  const justPlayedBubble = document.getElementById(`bubble_${activeSeat}`);
                  if (justPlayedBubble) {
                    setTimeout(() => {
                      justPlayedBubble.classList.remove('visible');
                    }, 1200);
                  }

                  isFinished = true;
                  try { reader.cancel(); } catch(e) {}
                  break;
                }
              } catch (parseErr) {
                console.error("SSE parse error", parseErr, line);
              }
            }
          }
        }

        // 如果连接中断且未收到 finish 事件，主动同步服务端最新局势
        if (!isFinished) {
          stopThinkingClock(activeSeat, null);
          if (statusPillEl) {
            statusPillEl.style.background = '#e84118';
            statusPillEl.innerText = '⚠️ 流式中断已同步';
          }
          try {
            const sRes = await fetch('/api/state');
            const syncedState = await sRes.json();
            updateUI(syncedState);
            finalStatus = syncedState.status;
          } catch(e) {}
        }
      } catch (err) {
        console.error("Stream step error:", err);
        stopThinkingClock(activeSeat, null);
      } finally {
        clearTimeout(abortTimer);
        isStepRunning = false;
        document.getElementById('btnNextStep').disabled = false;
      }
      return finalStatus;
    }

    async function toggleAutoPlay() {
      if (isAutoPlaying) {
        stopAutoPlay();
      } else {
        isAutoPlaying = true;
        document.getElementById('btnAuto').innerText = "⏸️ 暂停";
        document.getElementById('btnAuto').className = "secondary";
        runAutoLoop();
      }
    }

    async function runAutoLoop() {
      if (!isAutoPlaying) return;
      const status = await stepTurn();
      if (status === 'playing' && isAutoPlaying) {
        autoTimer = setTimeout(runAutoLoop, 2200);
      } else {
        stopAutoPlay();
      }
    }

    function stopAutoPlay() {
      isAutoPlaying = false;
      clearTimeout(autoTimer);
      document.getElementById('btnAuto').innerText = "⚡ 自动对战";
      document.getElementById('btnAuto').className = "danger";
    }

    async function exportForGemini() {
      try {
        const res = await fetch('/api/export_record');
        const data = await res.json();
        alert("✅ 本局完整对战记录已在后台保存就绪！\n\n你可以直接在 Antigravity 聊天窗口对我说：\n'Gemini，请对最新这一局斗地主进行深度战术复盘！'");
      } catch (e) {
        alert("获取对局记录出错: " + e);
      }
    }

    /* ============================================================
       🎬 赛后演播室 · 毒舌解说复盘引擎
       ============================================================ */
    let replayTurns = [];
    let currentReplayIdx = 0;
    let isReplayAuto = false;
    let replayTimer = null;
    let isReplayMode = false;

