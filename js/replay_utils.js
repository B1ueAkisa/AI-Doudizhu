// 扑克牌显示与卡牌数据解析工具函数
window.ReplayUtils = {
  computePlayerStats(gameData, turns) {
    if (!gameData || !turns || !turns.length) return [];
    const inHands = this.extractInitialHands(turns);
    const pSum = this.extractPlayerSummary(gameData.players_summary);
    const winner = gameData.winner || '';
    const winnerRole = gameData.winner_role || '';
    const landlord = gameData.landlord || '';

    const playedCount = { 0: 0, 1: 0, 2: 0 };
    turns.forEach(t => {
      if (!t) return;
      const s = t.seat?.includes('底部') ? 0 : (t.seat?.includes('右方') ? 1 : 2);
      if (t.actual_play && t.actual_play.length) {
        playedCount[s] += t.actual_play.length;
      }
    });

    const seatNames = { 0: '底部 · 主视角', 1: '右方 · 下家', 2: '左方 · 上家' };

    return [0, 1, 2].map(seat => {
      const summary = pSum[seat] || {};
      const model = summary.model || (seat === 0 ? 'GLM-4' : (seat === 1 ? 'Qwen2.5' : 'GLM-Z1'));
      const role = summary.role || (model === landlord ? '地主' : '农民');
      const initCards = (inHands[seat] && inHands[seat].length) ? inHands[seat].length : (role === '地主' ? 20 : 17);
      const played = playedCount[seat] || 0;
      const remaining = Math.max(0, initCards - played);
      const isWinner = (winner && model === winner) || (winnerRole && role.includes(winnerRole));

      return {
        seat,
        seatName: seatNames[seat],
        model,
        role,
        initCards,
        played,
        remaining,
        isWinner
      };
    });
  },

  defaultCommentators: [{
    id: 'gemini_flash',
    name: 'Gemini 2.5 Flash',
    icon: '⚡',
    role_title: '👑 首席毒舌判官 · 逻辑碎纸机',
    badge_color: '#be2edd',
    signature: '“牌如人生，菜是原罪。在逻辑崩塌的深渊里，没有一张牌是无辜的。” —— 署名：Gemini 2.5 Flash 审判席',
    post_match_review: {
      verdict_title: '【赛后总评】：51手抽象拉锯战，农民靠地主连环脑溢血完成奇迹屠龙！',
      mvp: 'GLM-Z1-Flash',
      golden_broom: '地主 Qwen',
      rating: '8.9 / 10',
      summary_text: '本局打足51手，战况极其激烈...',
      signature: '—— 首席判官 Gemini 2.5 Flash 亲笔签发'
    },
    turns_commentary: {}
  }],

  isRed(card) {
    if (!card) return false;
    return card.includes('♥') || card.includes('♦') || card === '大王';
  },

  getCardRank(card) {
    if (!card) return '';
    if (card.startsWith('♠') || card.startsWith('♥') || card.startsWith('♣') || card.startsWith('♦')) {
      return card.slice(1);
    }
    return card;
  },

  getCardSuit(card) {
    if (!card) return '';
    if (card.startsWith('♠') || card.startsWith('♥') || card.startsWith('♣') || card.startsWith('♦')) {
      return card[0];
    }
    if (card === '大王') return '👑';
    if (card === '小王') return '🃏';
    return '';
  },

  truncateCoT(raw, maxLen = 95) {
    if (!raw) return '';
    let clean = raw.replace(/<think>|<\/think>/g, '').trim();
    if (clean.length > maxLen) clean = clean.slice(0, maxLen) + '...';
    return clean;
  },

  getCascadeRows(cards, maxPerRow = 8) {
    if (!cards || !cards.length) return [];
    if (cards.length <= maxPerRow) return [cards];
    const half = Math.ceil(cards.length / 2);
    return [cards.slice(0, half), cards.slice(half)];
  },

  computeHands(initialHands, turns, currentStep) {
    const res = { 0: [...(initialHands[0] || [])], 1: [...(initialHands[1] || [])], 2: [...(initialHands[2] || [])] };
    if (currentStep <= 0) return res;
    for (let i = 0; i < currentStep; i++) {
      const t = turns[i];
      if (!t) continue;
      const s = t.seat.includes('底部') ? 0 : (t.seat.includes('右方') ? 1 : 2);
      if (t.actual_play && t.actual_play.length) {
        t.actual_play.forEach(card => {
          const idx = res[s].indexOf(card);
          if (idx !== -1) res[s].splice(idx, 1);
        });
      }
    }
    return res;
  },

  computeTrickCards(turns, currentStep) {
    const res = { 0: null, 1: null, 2: null };
    if (!turns || !turns.length || currentStep < 1) return res;
    let curIdx = currentStep - 1;
    let trickStartIdx = curIdx;
    while (trickStartIdx > 0 && turns[trickStartIdx].table_cards_before && turns[trickStartIdx].table_cards_before.length > 0) {
      trickStartIdx--;
    }
    for (let i = trickStartIdx; i <= curIdx; i++) {
      const t = turns[i];
      const s = t.seat.includes('底部') ? 0 : (t.seat.includes('右方') ? 1 : 2);
      res[s] = {
        cards: t.actual_play || [],
        model: t.model_name,
        playedStep: i + 1
      };
    }
    return res;
  },

  extractInitialHands(turns) {
    const inHands = { 0: [], 1: [], 2: [] };
    [0, 1, 2].forEach(seat => {
      for (let i = 0; i < (turns || []).length; i++) {
        const t = turns[i];
        const s = t.seat.includes('底部') ? 0 : (t.seat.includes('右方') ? 1 : 2);
        if (s === seat && t.hand_before && t.hand_before.length) {
          inHands[seat] = [...t.hand_before];
          break;
        }
      }
    });
    return inHands;
  },

  extractPlayerSummary(players_summary) {
    const pSum = { 0: null, 1: null, 2: null };
    if (players_summary) {
      players_summary.forEach(p => {
        const s = p.seat.includes('底部') ? 0 : (p.seat.includes('右方') ? 1 : 2);
        pSum[s] = p;
      });
    }
    return pSum;
  },

  exportRecord(data) {
    if (!data) return;
    const str = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
    const a = document.createElement('a');
    a.href = str;
    a.download = `牌谱_${data.game_id || 'replay'}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  },

  uploadJson(event, callback) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        if (callback) callback(data, file.name);
      } catch (err) {
        alert("解析牌谱 JSON 失败: " + err);
      }
    };
    reader.readAsText(file);
  }
};
