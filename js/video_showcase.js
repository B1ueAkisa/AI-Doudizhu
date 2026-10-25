    const scenes = document.querySelectorAll('.scene');
    const dots = document.querySelectorAll('.nav-dot');
    const progressBar = document.getElementById('progress-bar');
    const btnPlayPause = document.getElementById('btn-play-pause');

    let currentScene = 0;
    const totalScenes = scenes.length;

    // 各段语音配音文件名与严格实测精准时长对应表 (精准毫秒级，绝不提前切走)
    const audioClips = [
      "scene_intro_fast",
      "scene1_build",
      "scene2_rules",
      "scene3_players",
      "scene4_commentators",
      "scene_outro_fast"
    ];

    // 实测精准时长 (毫秒，scene_intro_fast 为 17.28s，scene_outro_fast 为 24.89s)
    const exactDurations = [43050, 33050, 35300, 27750, 25150, 29200];
    const totalDuration = exactDurations.reduce((a, b) => a + b, 0);

    let currentAudio = null;
    let isPlaying = true;
    let audioFallbackTimer = null;
    let globalTimer = null;
    let accumulatedTime = 0;
    let playbackSpeed = 1.25;
    let onClipFinishedRef = null;

    function setSpeed(rate) {
      playbackSpeed = parseFloat(rate);
      console.log(`[Playback] 语速调整为: ${playbackSpeed}x`);

      // 联动更新页面上所有倍速按钮高亮状态
      document.querySelectorAll('.btn-speed-rate').forEach(btn => {
        if (parseFloat(btn.dataset.rate) === playbackSpeed) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // 实时应用到当前播放的音频
      if (currentAudio) {
        currentAudio.playbackRate = playbackSpeed;

        // 重新校准当前场景的安全保底定时器
        const durSec = (currentAudio.duration && !isNaN(currentAudio.duration)) ? currentAudio.duration : (exactDurations[currentScene] / 1000);
        setupSceneSafetyTimer(durSec);
      }
    }

    function switchScene(index) {
      if (index < 0 || index >= totalScenes) return;

      scenes.forEach(s => s.classList.remove('active'));
      dots.forEach(d => d.classList.remove('active'));

      currentScene = index;
      if (scenes[currentScene]) scenes[currentScene].classList.add('active');
      if (dots[currentScene]) dots[currentScene].classList.add('active');

      playCurrentSceneAudio();
    }

    function setupSceneSafetyTimer(durationSec) {
      if (audioFallbackTimer) clearTimeout(audioFallbackTimer);
      // 以真实音频时长 + 4 秒宽限保底，绝不在播放中截断！
      const safeMs = Math.round(((durationSec || 20) * 1000 + 4000) / playbackSpeed);
      audioFallbackTimer = setTimeout(() => {
        if (currentAudio && !currentAudio.paused && !currentAudio.ended) {
          console.log(`[Audio Guard] 场景 ${currentScene} 仍在正常播音中，绝不提前切走`);
          return;
        }
        console.warn(`[Audio Fallback] 场景 ${currentScene} 触发保底切换`);
        if (typeof onClipFinishedRef === 'function') onClipFinishedRef();
      }, safeMs);
    }

    function playCurrentSceneAudio() {
      // 停止上一个音频
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }
      if (audioFallbackTimer) {
        clearTimeout(audioFallbackTimer);
        audioFallbackTimer = null;
      }

      if (currentScene >= totalScenes) {
        finishShow();
        return;
      }

      const clipName = audioClips[currentScene];
      const audioUrl = `/videos/audio/${clipName}.mp3`;
      const expectedMs = exactDurations[currentScene] || 18000;

      currentAudio = new Audio(audioUrl);
      currentAudio.playbackRate = playbackSpeed;
      let advanceTriggered = false;

      function onClipFinished() {
        if (advanceTriggered) return;
        advanceTriggered = true;
        console.log(`[Audio] ${clipName} 完整播放完毕，准备切下一幕...`);
        const breathe = Math.max(300, 800 / playbackSpeed); // 给足 800ms 呼吸缓冲
        setTimeout(() => {
          if (currentScene === 0) {
            // 片头完整播毕（17秒） -> 优雅平滑切入完整牌桌实况复盘 (replay.html)！
            console.log("片头完整播毕，平滑切入 43 手完整牌桌实况复盘 (replay.html)...");
            window.location.href = `/replay.html?auto=1&speed=${playbackSpeed}`;
            return;
          }
          if (currentScene < totalScenes - 1) {
            switchScene(currentScene + 1);
          } else {
            finishShow();
          }
        }, breathe);
      }
      onClipFinishedRef = onClipFinished;

      // 自然播毕事件驱动
      currentTurnAudio = currentAudio;
      currentAudio.onended = onClipFinished;

      // 默认挂载基于配置表的宽限保底
      setupSceneSafetyTimer(expectedMs / 1000);

      // 元数据加载完毕后，用音频真实物理时长动态校准
      currentAudio.addEventListener('loadedmetadata', () => {
        if (currentAudio && currentAudio.duration && !isNaN(currentAudio.duration)) {
          setupSceneSafetyTimer(currentAudio.duration);
        }
      });

      if (isPlaying) {
        currentAudio.play().then(() => {
          hideAutoplayGate();
          console.log(`[AUDIO_EVENT] START:${clipName}:${Date.now()}`);
        }).catch(e => {
          console.warn(`[Audio Autoplay] 浏览器阻止自动播放，弹出唤醒浮层:`, e);
          showAutoplayGate();
        });
      }
    }

    function showAutoplayGate() {
      const gate = document.getElementById('autoplay-gate');
      if (gate) gate.style.display = 'flex';
    }

    function hideAutoplayGate() {
      const gate = document.getElementById('autoplay-gate');
      if (gate) gate.style.display = 'none';
    }

    function unlockAutoplay() {
      hideAutoplayGate();
      if (currentAudio) {
        currentAudio.play().then(() => {
          isPlaying = true;
          btnPlayPause.innerText = "⏸ 暂停";
        }).catch(err => console.error("Play failed after click:", err));
      }
    }

    function finishShow() {
      console.log("SHOWCASE_PRESENTATION_FINISHED");
      console.log(`[RECORDING_FINISHED] ${Date.now()}`);
      window.__presentationFinished = true;
      if (globalTimer) clearInterval(globalTimer);
    }

    function nextScene() {
      if (currentScene === 0) {
        window.location.href = `/replay.html?auto=1&speed=${playbackSpeed}`;
        return;
      }
      if (currentScene < totalScenes - 1) {
        switchScene(currentScene + 1);
      } else {
        finishShow();
      }
    }

    function prevScene() {
      if (currentScene > 0) {
        switchScene(currentScene - 1);
      } else {
        switchScene(0);
      }
    }

    function togglePlay() {
      isPlaying = !isPlaying;
      btnPlayPause.innerText = isPlaying ? "⏸ 暂停" : "▶ 播放";
      if (currentAudio) {
        if (isPlaying) currentAudio.play();
        else currentAudio.pause();
      }
    }

    // 进度条平滑递增
    let progressStartTime = Date.now();
    function tickProgress() {
      if (!isPlaying) return;
      // 计算累积时间
      let passedBefore = 0;
      for (let i = 0; i < currentScene; i++) {
        passedBefore += exactDurations[i];
      }
      let currentClipProgress = 0;
      if (currentAudio && !isNaN(currentAudio.currentTime)) {
        currentClipProgress = currentAudio.currentTime * 1000;
      }
      const totalPassed = Math.min(passedBefore + currentClipProgress, totalDuration);
      const pct = (totalPassed / totalDuration) * 100;
      progressBar.style.width = pct + '%';
    }
    globalTimer = setInterval(tickProgress, 100);

    // 页面加载完毕即开播 (支持 ?scene=9 直接定位终幕致谢)
    window.addEventListener('load', () => {
      const urlParams = new URLSearchParams(window.location.search);
      const sceneParam = urlParams.get('scene');
      const speedParam = urlParams.get('speed');
      if (speedParam) {
        setSpeed(parseFloat(speedParam) || 1.25);
      } else {
        setSpeed(1.25);
      }
      if (sceneParam === '9' || sceneParam === 'outro' || sceneParam === '5' || window.location.hash === '#scene-outro' || window.location.hash === '#scene-9') {
        console.log("直接进入赛后终幕总结与致谢...");
        switchScene(5);
      } else {
        switchScene(0);
      }
    });
