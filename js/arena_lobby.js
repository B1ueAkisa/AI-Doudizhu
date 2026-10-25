// 竞技场开局大厅与选手真机握手检录模块
    function openLobbyModal() {
      stopAutoPlay();
      document.getElementById('lobbyModal').style.display = 'flex';
      document.getElementById('btnEnterGame').disabled = true;
    }

    async function runHandshakeCheck() {
      const btn = document.getElementById('btnHandshake');
      btn.disabled = true;
      btn.innerText = "⏳ 正在真机连接并获取开场白...";

      const models = [
        document.getElementById('lobbySel0').value,
        document.getElementById('lobbySel1').value,
        document.getElementById('lobbySel2').value
      ];

      const seatNames = ['底部 · 主视角', '右方 · 下家', '左方 · 上家'];
      const seatColors = ['var(--seat-0-color)', 'var(--seat-1-color)', 'var(--seat-2-color)'];

      [0, 1, 2].forEach(i => {
        document.getElementById(`status${i}`).innerHTML = `<span class="status-pending" style="color:#fbc531;">📡 正在单独连接【${models[i]}】...</span>`;
      });

      const successArray = [false, false, false];

      // 并发独立握手检测：出几多显示几多，绝不等待全部！
      const tasks = models.map((m, idx) => {
        return fetch('/api/handshake_single', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({seat_idx: idx, model: m})
        })
        .then(res => res.json())
        .then(r => {
          const sEl = document.getElementById(`status${idx}`);
          if (r.success) {
            successArray[idx] = true;
            sEl.innerHTML = `
              <span class="status-success" style="color:#2ed573;">✅ 连接畅通 (${r.latency})</span>
              <div style="font-size:12px;color:#f5f6fa;margin-top:5px;font-style:italic;line-height:1.4;">"${r.greeting}"</div>
            `;
          } else {
            successArray[idx] = false;
            sEl.innerHTML = `
              <span class="status-fail" style="color:#ff4757;">❌ 连接异常: ${r.error}</span>
              <div style="font-size:11px;color:#ff7675;margin-top:2px;">建议切换为 GLM-4-Flash 备用</div>
            `;
          }
        })
        .catch(err => {
          const sEl = document.getElementById(`status${idx}`);
          sEl.innerHTML = `<span class="status-fail" style="color:#ff4757;">❌ 网络异常: ${err}</span>`;
        });
      });

      await Promise.all(tasks);

      btn.disabled = false;
      btn.innerText = "⚡ 重新握手测试";

      if (successArray.every(Boolean)) {
        document.getElementById('btnEnterGame').disabled = false;
      } else {
        alert("部分模型握手失败，建议将异常席位切换为智谱 GLM-4-Flash 或通义 7B 重试！");
      }
    }

    async function enterGame() {
      const m0 = document.getElementById('lobbySel0').value;
      const m1 = document.getElementById('lobbySel1').value;
      const m2 = document.getElementById('lobbySel2').value;

      try {
        const res = await fetch('/api/set_lineup', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({models: [m0, m1, m2]})
        });
        const state = await res.json();
        document.getElementById('lobbyModal').style.display = 'none';
        updateUI(state);
      } catch (e) {
        alert("开局失败: " + e);
      }
    }

