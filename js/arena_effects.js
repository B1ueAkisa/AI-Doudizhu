// 竞技场卡牌渲染、飞牌动画、打字机与炸弹特效模块
    function renderCard(cardStr, isMedium = false, zIndex = 1) {
      if (!cardStr) return '';
      let isRed = cardStr.includes('♥') || cardStr.includes('♦') || cardStr === '大王';
      let suit = '';
      let rank = cardStr;
      if (cardStr.startsWith('♠') || cardStr.startsWith('♥') || cardStr.startsWith('♣') || cardStr.startsWith('♦')) {
        suit = cardStr[0];
        rank = cardStr.slice(1);
      }
      return `
        <div class="poker-card ${isRed ? 'red' : 'black'} ${isMedium ? 'card-medium' : ''}" style="z-index:${zIndex};">
          <div class="card-top">${rank}</div>
          <div class="card-suit">${suit || (cardStr === '大王' ? '👑' : '🃏')}</div>
        </div>
      `;
    }

    function animateCardThrow(seatIdx, cardStrings) {
      const pod = document.getElementById(`pod_${seatIdx}`);
      const targetZone = document.getElementById(`played_zone_${seatIdx}`);
      if (!pod || !cardStrings || !cardStrings.length) return;

      const podRect = pod.getBoundingClientRect();
      let targetX = 0, targetY = 0;

      if (targetZone) {
        const targetRect = targetZone.getBoundingClientRect();
        if (targetRect.width > 0 && targetRect.height > 0) {
          targetX = (targetRect.left + targetRect.width / 2) - (podRect.left + podRect.width / 2);
          targetY = (targetRect.top + targetRect.height / 2) - (podRect.top + podRect.height / 2);
        }
      }

      // 兜底几何计算
      if (targetX === 0 && targetY === 0) {
        if (seatIdx === 0) { targetX = 0; targetY = -120; }
        else if (seatIdx === 1) { targetX = -120; targetY = 80; }
        else if (seatIdx === 2) { targetX = 120; targetY = 80; }
      }

      const ghost = document.createElement('div');
      ghost.className = 'flying-card-ghost';
      ghost.innerHTML = cardStrings.map(c => renderCard(c, true)).join('');
      ghost.style.left = (podRect.left + podRect.width / 2 - 40) + 'px';
      ghost.style.top = (podRect.top + podRect.height / 2 - 40) + 'px';
      document.body.appendChild(ghost);

      requestAnimationFrame(() => {
        ghost.style.transform = `translate3d(${targetX}px, ${targetY}px, 0) scale(1.08) rotate(${(Math.random()*12)-6}deg)`;
        ghost.style.opacity = '1';
      });

      setTimeout(() => { ghost.remove(); }, 420);
    }

    function toggleCot(btn) {
      const card = btn.closest('.stream-card');
      if (!card) return;
      const cotBody = card.querySelector('.live-cot-text');
      if (!cotBody) return;
      if (cotBody.style.display === 'none' || getComputedStyle(cotBody).display === 'none') {
        cotBody.style.display = 'block';
        btn.innerHTML = `🔼 收起思维链`;
        btn.classList.add('expanded');
      } else {
        cotBody.style.display = 'none';
        const charCount = cotBody.innerText.length;
        btn.innerHTML = `🔽 展开查看完整思维链 (${charCount} 字)`;
        btn.classList.remove('expanded');
      }
    }

    /* 打字机流式输出文本 */
    function streamTypewriter(element, text, speed = 15) {
      element.innerText = '';
      let i = 0;
      const timer = setInterval(() => {
        if (i < text.length) {
          element.innerText += text.charAt(i);
          i++;
        } else {
          clearInterval(timer);
        }
      }, speed);
    }

    async function loadRoster() {
      try {
        const res = await fetch('/api/roster');
        roster = await res.json();
        ['lobbySel0', 'lobbySel1', 'lobbySel2'].forEach((selId, i) => {
          const sel = document.getElementById(selId);
          sel.innerHTML = Object.keys(roster).map(k => `<option value="${k}">${k} (${roster[k].desc})</option>`).join('');
          if (i === 0) sel.value = "GLM-4-Flash";
          if (i === 1) sel.value = "GLM-Z1-Flash";
          if (i === 2) sel.value = "Qwen/Qwen2.5-7B-Instruct";
        });
      } catch (e) {
        console.error(e);
      }
    }

    function triggerBombEffect() {
      const overlay = document.getElementById('bombOverlay');
      const table = document.getElementById('mainTable');
      overlay.className = 'bomb-overlay show';
      table.className = 'table-container screen-shake';
      setTimeout(() => {
        overlay.className = 'bomb-overlay';
        table.className = 'table-container';
      }, 1200);
    }

