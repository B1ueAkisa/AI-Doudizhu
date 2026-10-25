/**
 * 赛后复盘演播室 - Vue 核心调度应用
 * 支持：
 * 1. 多AI解说嘉宾动态切换 (Gemini 2.5 Flash, DeepSeek-R1, GPT-4o)
 * 2. 赛后全盘深度战术总评 & 专属人设与签名
 * 3. 逐手打字机流式解说与长考推演还原
 * 4. 靶向思维链断点剖析与伏笔双闪聚光灯
 */
const { createApp, ref, computed, watch, onMounted } = Vue;
createApp({
  setup() {
    const gameData = ref(null);
    const turns = ref([]);
    const currentStep = ref(0);
    const currentLoadedTitle = ref("AI 斗地主精彩对局复盘");
    const initialHands = ref({ 0: [], 1: [], 2: [] });
    const playerSummary = ref({ 0: null, 1: null, 2: null });
    const bottomCards = ref([]);
    // 多AI解说嘉宾系统
    const activeCommentatorId = ref('gemini_flash');
    const showReviewModal = ref(false);
    // 吐槽打字机
    const roastDisplayText = ref("正在载入解说...");
    const isTypewriting = ref(false);
    let typewriterTimer = null;
    // 自动播放与分步状态
    const isPlaying = ref(false);
    const speedMultiplier = ref(1.25);
    const turnPhase = ref('decided'); // 'thinking' 或 'decided'
    let autoPlayTimer = null;
    let stepPhaseTimer = null;
    // 牌谱库弹窗
    const showLibModal = ref(false);
    const currentLibTab = ref('commented');
    const libRecords = ref([]);
    // 🎬 节目开场片头动画 & 录屏工具状态
    const showIntroModal = ref(false);
    const currentIntroStep = ref(1);
    const isRecording = ref(false);
    const recordTimerText = ref('00:00');
    // 计算属性：当前全部可用解说嘉宾
    const availableCommentators = computed(() => {
      if (gameData.value?.commentators && gameData.value.commentators.length > 0) {
        return gameData.value.commentators;
      }
      return window.ReplayUtils?.defaultCommentators || [];
    });
    // 当前选中的解说嘉宾
    const currentCommentator = computed(() => {
      return availableCommentators.value.find(c => c.id === activeCommentatorId.value) || availableCommentators.value[0];
    });
    // 当前手牌数据
    const currentTurn = computed(() => {
      if (!turns.value.length || currentStep.value < 1) return null;
      return turns.value[currentStep.value - 1] || null;
    });
    const activeSeat = computed(() => {
      if (!currentTurn.value) return -1;
      const s = currentTurn.value.seat || '';
      return s.includes('底部') ? 0 : (s.includes('右方') ? 1 : 2);
    });
    const currentTurnActionText = computed(() => {
      if (!currentTurn.value) return '';
      const ap = currentTurn.value.actual_play;
      return ap && ap.length ? ap.join(' ') : '不出 (PASS)';
    });
    // 核心反应式计算：当前步骤下三家的实时剩余手牌与桌面牌
    const hands = computed(() => window.ReplayUtils?.computeHands(initialHands.value, turns.value, currentStep.value) || { 0:[], 1:[], 2:[] });
    const trickCards = computed(() => window.ReplayUtils?.computeTrickCards(turns.value, currentStep.value) || { 0:null, 1:null, 2:null });
    // 中央领牌状态文字
    const trickStatusText = computed(() => {
      if (currentStep.value === 0) {
        const landlord = gameData.value?.landlord || '地主';
        return `🃏 发牌就绪 · 全员满手牌 · 等待地主【${landlord}】开局首拔`;
      }
      if (!currentTurn.value) return '等待发牌';
      const t = currentTurn.value;
      if (turnPhase.value === 'thinking') {
        const durStr = t.duration_sec ? t.duration_sec.toFixed(1) + 's' : '长考中';
        return `⏳ 【${t.model_name}】正在深思推演牌型 (实况长考 ${durStr})...`;
      }
      if (t.table_cards_before && t.table_cards_before.length) {
        return `桌面当前需要压制：【${t.table_cards_before.join(' ')}】`;
      }
      return t.actual_play && t.actual_play.length
        ? `新一轮首发：由【${t.model_name}】打出【${t.actual_play.join(' ')}】`
        : `牌权在手，等待首发出牌`;
    });
    // 获取当前步针对当前解说员的解说词
    function getCommentaryForStep(step) {
      if (step === 0) {
        const landlordName = gameData.value?.landlord || "地主选手";
        const bottomStr = (bottomCards.value || []).join(' ') || "底牌在案";
        return `🎮 战局复位就绪！三家发牌完毕，本局地主由【${landlordName}】担任，获得底牌 [${bottomStr}]。全员手牌完整，一张未发！请点击【▶️ 自动解说】或【⏭️ 下一手】开启激战！`;
      }
      const t = turns.value[step - 1];
      if (!t) return `第 ${step} 手：局势扑朔迷离！`;
      const comm = currentCommentator.value;
      if (comm && comm.turns_commentary && comm.turns_commentary[String(step)]) {
        const item = comm.turns_commentary[String(step)];
        return item.commentary || item;
      }
      return t.gemini_commentary || t.commentary || `第 ${step} 手：局势扑朔迷离！`;
    }
    // 获取当前步针对当前解说员的伏笔/翻车判定
    const currentTurnBlunder = computed(() => {
      if (!currentTurn.value) return null;
      const step = currentStep.value;
      const comm = currentCommentator.value;
      if (comm && comm.turns_commentary && comm.turns_commentary[String(step)]) {
        const item = comm.turns_commentary[String(step)];
        if (item && item.is_blunder) {
          return {
            is_blunder: true,
            title: item.blunder_title || '【逆天伏笔】',
            tag: item.blunder_tag || '🚨 逆天脑回路',
            quote: item.blunder_quote || ''
          };
        }
      }
      if (currentTurn.value.is_blunder) {
        return {
          is_blunder: true,
          title: currentTurn.value.blunder_title || '【逆天伏笔】',
          tag: currentTurn.value.blunder_tag || '🚨 逆天脑回路',
          quote: currentTurn.value.blunder_quote || ''
        };
      }
      return null;
    });
    // 切换解说嘉宾
    function switchCommentator(commId) {
      activeCommentatorId.value = commId;
      const comment = getCommentaryForStep(currentStep.value);
      runTypewriter(comment, 18);
    }
    // 卡牌花色与样式辅助函数
    const { isRed, getCardRank, getCardSuit, truncateCoT, getCascadeRows } = window.ReplayUtils || {};
    // 打字机流式输出
    function runTypewriter(text, speed = 18) {
      if (typewriterTimer) clearTimeout(typewriterTimer);
      roastDisplayText.value = '';
      isTypewriting.value = true;
      let i = 0;
      function tick() {
        if (i < text.length) {
          roastDisplayText.value = text.slice(0, i + 1);
          i++;
          typewriterTimer = setTimeout(tick, speed);
        } else {
          roastDisplayText.value = text;
          isTypewriting.value = false;
        }
      }
      tick();
    }
    // 步骤控制
    function nextStep() {
      stopAutoPlay();
      if (currentStep.value < turns.value.length) {
        currentStep.value++;
      } else {
        triggerSettlementModal();
      }
    }
    function prevStep() {
      stopAutoPlay();
      if (currentStep.value > 0) currentStep.value--;
    }
    function restart() {
      stopAutoPlay();
      currentStep.value = 0;
    }
    function onSliderInput(e) {
      stopAutoPlay();
      currentStep.value = parseInt(e.target.value);
    }
    // ============================================================
    // 🎙️ 完整实况录像声画同步引擎 (粤语解说关键手配音 + 自动步进)
    // ============================================================
    // 30手精准关键手与战犯剖析配音表
    const audioTurns = [1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 25, 28, 30, 32, 33, 35, 36, 37, 39, 40, 41, 42, 43];
    let currentTurnAudio = null;
    let turnAudioTimer = null;
    const isAutoTour = ref(false);
    const showFinishOverlay = ref(false);
    const autoSummaryTimerSec = ref(6);
    let summaryCountdownTimer = null;
    const settlementStats = computed(() => {
      return window.ReplayUtils?.computePlayerStats(gameData.value, turns.value) || [];
    });
    window.__triggerSettlementModal = triggerSettlementModal;
    function triggerSettlementModal() {
      showFinishOverlay.value = true;
      autoSummaryTimerSec.value = 6;
      if (summaryCountdownTimer) clearInterval(summaryCountdownTimer);
      summaryCountdownTimer = setInterval(() => {
        if (autoSummaryTimerSec.value > 1) {
          autoSummaryTimerSec.value--;
        } else {
          clearInterval(summaryCountdownTimer);
          goToSummary();
        }
      }, Math.round(1000 / speedMultiplier.value));
    }
    const isVoiceEnabled = ref(true);
    // 严谨判断：仅当前载入牌谱明确拥有配音时，才开启语音！绝不跨牌谱串音！
    const hasAudioVoice = computed(() => {
      if (!gameData.value) return false;
      if (gameData.value.has_turn_audio === true) return true;
      const title = currentLoadedTitle.value || '';
      return title.includes('43手');
    });
    function setReplaySpeed(val) {
      speedMultiplier.value = parseFloat(val);
      if (currentTurnAudio) {
        currentTurnAudio.playbackRate = speedMultiplier.value;
      }
    }
    function stopCurrentAudio() {
      if (currentTurnAudio) {
        currentTurnAudio.pause();
        currentTurnAudio = null;
      }
      if (turnAudioTimer) {
        clearTimeout(turnAudioTimer);
        turnAudioTimer = null;
      }
    }
    // 自动解说调度
    function toggleAutoPlay() {
      if (isPlaying.value) stopAutoPlay();
      else startAutoPlay();
    }
    function startAutoPlay() {
      if (currentStep.value >= turns.value.length) currentStep.value = 0;
      isPlaying.value = true;
      scheduleAudioSyncedTick();
    }
    function stopAutoPlay() {
      isPlaying.value = false;
      clearTimeout(autoPlayTimer);
      clearTimeout(stepPhaseTimer);
      stopCurrentAudio();
      turnPhase.value = 'decided';
    }
    function scheduleAudioSyncedTick() {
      if (!isPlaying.value) return;
      clearTimeout(autoPlayTimer);
      stopCurrentAudio();
      const step = currentStep.value;
      if (step === 0) {
        // 开局展示底牌和手牌，给 1.5 秒缓冲后自动开打第 1 手
        autoPlayTimer = setTimeout(() => {
          if (isPlaying.value) currentStep.value = 1;
        }, Math.max(1000, 1600 / speedMultiplier.value));
        return;
      }
      // 如果步数已严格超过总手数 (第 43 手已经播毕推进)
      if (step > turns.value.length) {
        stopAutoPlay();
        if (hasAudioVoice.value) {
          triggerSettlementModal();
        } else {
          roastDisplayText.value = `🏆 本局 ${turns.value.length} 手纯文字复盘结束！感谢收看！`;
        }
        return;
      }
      // 检查当前步数是否有独立配音，且【当前载入的对局】确实拥有专属配音！
      if (hasAudioVoice.value && isVoiceEnabled.value && audioTurns.includes(step)) {
        const audioDir = gameData.value?.turn_audio_dir || '/videos/audio/game2_turns';
        const audioUrl = `${audioDir}/turn_${step}.mp3`;
        currentTurnAudio = new Audio(audioUrl);
        currentTurnAudio.playbackRate = speedMultiplier.value;
        let advanced = false;
        function finishThisStep() {
          if (advanced) return;
          advanced = true;
          stopCurrentAudio();
          const breathe = Math.max(300, 700 / speedMultiplier.value);
          setTimeout(() => {
            if (isPlaying.value) {
              if (currentStep.value < turns.value.length) {
                currentStep.value++;
              } else {
                stopAutoPlay();
                triggerSettlementModal();
              }
            }
          }, breathe);
        }
        currentTurnAudio.onended = finishThisStep;
        // 动态安全保底定时器：严格以真实时长 + 4秒安全冗余，且播放中绝不截断！
        function setupSafetyTimer(durationSec) {
          if (turnAudioTimer) clearTimeout(turnAudioTimer);
          const safeMs = Math.round(((durationSec || 20) * 1000 + 4000) / speedMultiplier.value);
          turnAudioTimer = setTimeout(() => {
            if (currentTurnAudio && !currentTurnAudio.paused && !currentTurnAudio.ended) {
              console.log(`[Audio Guard] Turn ${step} 仍在播音中，绝不强行截断`);
              return;
            }
            console.warn(`[Audio Timeout] Turn ${step} 触发保底推进`);
            finishThisStep();
          }, safeMs);
        }
        // 默认预设 35 秒宽限保底（覆盖最长 25.8 秒的解说）
        setupSafetyTimer(35);
        // 监听到元数据后，精准校准为：音频实际秒数 + 4秒安全冗余
        currentTurnAudio.addEventListener('loadedmetadata', () => {
          if (currentTurnAudio && currentTurnAudio.duration && !isNaN(currentTurnAudio.duration)) {
            setupSafetyTimer(currentTurnAudio.duration);
          }
        });
        currentTurnAudio.play().then(() => {
          console.log(`[AUDIO_EVENT] START:turn_${step}:${Date.now()}`);
        }).catch(e => {
          console.warn(`[Audio Autoplay] 浏览器阻止自动播放，启用定时推进:`, e);
          finishThisStep();
        });
      } else {
        // 无配音模式（包括其他未配音的牌谱，或当前非关键手，或用户静音）：
        // 绝不乱调用其他牌谱的配音！按字数长短自适应推进
        const comment = getCommentaryForStep(step);
        const textLen = (comment || '').length;
        const textDelay = Math.max(1000, Math.min(3800, textLen * 45 + 850)) / speedMultiplier.value;
        autoPlayTimer = setTimeout(() => {
          if (isPlaying.value) {
            if (currentStep.value < turns.value.length) {
              currentStep.value++;
            } else {
              stopAutoPlay();
              triggerSettlementModal();
            }
          }
        }, textDelay);
      }
    }
    function goToSummary() {
      window.location.href = `/video_showcase.html?scene=9&speed=${speedMultiplier.value}`;
    }
    function onSpeedChange() {
      if (isPlaying.value) scheduleAudioSyncedTick();
    }
    watch(currentStep, (newVal) => {
      clearTimeout(stepPhaseTimer);
      stopCurrentAudio();
      if (newVal === 0) {
        turnPhase.value = 'decided';
        const landlordName = gameData.value?.landlord || "地主选手";
        const bottomStr = (bottomCards.value || []).join(' ') || "底牌在案";
        const initComment = `🎮 战局复位就绪！三家发牌完毕，本局地主由【${landlordName}】担任，获得底牌 [${bottomStr}]。全员手牌完整，一张未发！正片完整实况开打！`;
        runTypewriter(initComment, 18);
        if (isPlaying.value) scheduleAudioSyncedTick();
        return;
      }
      const t = turns.value[newVal - 1];
      turnPhase.value = 'decided';
      const comment = getCommentaryForStep(newVal);
      runTypewriter(comment, 18);
      if (isPlaying.value) {
        scheduleAudioSyncedTick();
      }
    });
    // 载入对局数据
    async function loadGame(url = '/api/replay_record', title = null) {
      stopAutoPlay();
      try {
        const res = await fetch(url);
        const data = await res.json();
        setupGame(data, title);
      } catch (e) {
        alert("加载牌谱失败: " + e);
      }
    }
    function setupGame(data, title = null) {
      gameData.value = data;
      turns.value = data.turns_record || data.turns || [];
      if (title) currentLoadedTitle.value = title;
      else if (data.title) currentLoadedTitle.value = data.title;
      else if (data.commentary_title) currentLoadedTitle.value = data.commentary_title;
      else currentLoadedTitle.value = `对局 #${data.game_id || ''} (${turns.value.length}手对局)`;
      bottomCards.value = data.bottom_cards || [];
      playerSummary.value = window.ReplayUtils?.extractPlayerSummary(data.players_summary) || { 0:null, 1:null, 2:null };
      initialHands.value = window.ReplayUtils?.extractInitialHands(turns.value) || { 0:[], 1:[], 2:[] };
      // 初始化解说员
      if (data.commentators && data.commentators.length > 0) {
        activeCommentatorId.value = data.active_commentator_id || data.commentators[0].id;
      }
      currentStep.value = 0;
      const landlordName = data.landlord || "地主选手";
      const bottomStr = (data.bottom_cards || []).join(' ') || "底牌在案";
      const firstComment = `🎮 战局准备就绪！三家发牌完毕，本局地主由【${landlordName}】担任，获得底牌 [${bottomStr}]。全员手牌完整，一张未发！请点击【▶️ 自动解说】或【⏭️ 下一手】开启激战！`;
      runTypewriter(firstComment, 18);
    }
    // 牌谱库弹窗与选择
    async function openLibModal() {
      showLibModal.value = true;
      await fetchLibRecords();
    }
    function switchLibTab(tab) {
      currentLibTab.value = tab;
      fetchLibRecords();
    }
    async function fetchLibRecords() {
      try {
        const res = await fetch('/api/records_list');
        const data = await res.json();
        libRecords.value = currentLibTab.value === 'commented' ? data.commented : data.raw;
      } catch (e) {
        console.error("获取牌谱列表失败", e);
      }
    }
    async function selectRecord(rec) {
      showLibModal.value = false;
      const url = `/api/load_record?type=${encodeURIComponent(rec.type)}&filename=${encodeURIComponent(rec.filename)}`;
      await loadGame(url, rec.title);
    }
    function onLocalJsonUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target.result);
          setupGame(data, file.name.replace('.json', ''));
          showLibModal.value = false;
        } catch (err) {
          alert("解析本地 JSON 文件失败: " + err);
        }
      };
      reader.readAsText(file);
    }
    function goToLive() {
      window.location.href = '/';
    }
    function exportCurrentRecord() {
      if (!gameData.value) return;
      const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(gameData.value, null, 2));
      const a = document.createElement('a');
      a.setAttribute("href", jsonStr);
      a.setAttribute("download", `斗地主复盘_${currentLoadedTitle.value}.json`);
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    // 🎬 赛事导播大赏展示大屏直达
    function openIntroModal() {
      window.location.href = '/video_showcase.html';
    }
    // 🎥 录屏模块组件挂载
    const recorder = (window.initScreenRecorder ? window.initScreenRecorder(isRecording, recordTimerText) : {
      startScreenRecording: () => {},
      stopScreenRecording: () => {},
      toggleScreenRecording: () => {}
    });
    onMounted(() => {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('speed')) {
        speedMultiplier.value = parseFloat(urlParams.get('speed')) || 1.25;
      } else {
        speedMultiplier.value = 1.25;
      }
      loadGame().then(() => {
        if (urlParams.get('auto') === '1') {
          console.log("[Replay] 自动实况声画模式开启...");
          isAutoTour.value = true;
          setTimeout(() => {
            startAutoPlay();
          }, 800);
        } else if (urlParams.get('intro') === '1') {
          showIntroModal.value = true;
        }
      });
    });
    return {
      gameData,
      turns,
      currentStep,
      currentLoadedTitle,
      hands,
      trickCards,
      trickStatusText,
      playerSummary,
      bottomCards,
      currentTurn,
      activeSeat,
      currentTurnActionText,
      // 多解说员
      availableCommentators,
      activeCommentatorId,
      currentCommentator,
      currentTurnBlunder,
      switchCommentator,
      showReviewModal,
      // 控制
      isPlaying,
      speedMultiplier,
      turnPhase,
      roastDisplayText,
      isTypewriting,
      nextStep,
      prevStep,
      restart,
      onSliderInput,
      toggleAutoPlay,
      onSpeedChange,
      setReplaySpeed,
      isAutoTour,
      hasAudioVoice,
      isVoiceEnabled,
      showFinishOverlay,
      settlementStats,
      autoSummaryTimerSec,
      goToSummary,
      // 弹窗
      showLibModal,
      currentLibTab,
      libRecords,
      openLibModal,
      switchLibTab,
      selectRecord,
      onLocalJsonUpload,
      goToLive,
      exportCurrentRecord,
      // 辅助
      isRed,
      getCardRank,
      getCardSuit,
      getAvatarSvg,
      truncateCoT,
      getCascadeRows,
      // 🎬 节目开场片头 & 🎥 录屏出片
      openIntroModal,
      isRecording,
      recordTimerText,
      toggleScreenRecording: recorder.toggleScreenRecording,
      startScreenRecording: recorder.startScreenRecording,
      stopScreenRecording: recorder.stopScreenRecording
    };
  }
}).mount('#app');
