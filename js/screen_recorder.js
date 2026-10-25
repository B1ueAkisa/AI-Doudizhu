// 原生浏览器高清录屏管理模块 (MediaRecorder API)
window.initScreenRecorder = function(isRecordingRef, recordTimerTextRef) {
  let mediaRecorder = null;
  let recordedChunks = [];
  let recordTimerInterval = null;
  let recordStartTime = 0;

  async function startScreenRecording() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        alert("当前浏览器环境不支持原生屏幕捕获，建议使用最新版 Chrome / Edge 浏览器！");
        return;
      }

      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          displaySurface: 'browser',
          frameRate: { ideal: 60, max: 60 }
        },
        audio: true
      });

      recordedChunks = [];
      let mimeType = 'video/webm;codecs=vp9,opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm';
      }

      mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          recordedChunks.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        saveRecording();
        isRecordingRef.value = false;
        if (recordTimerInterval) clearInterval(recordTimerInterval);
        stream.getTracks().forEach(t => t.stop());
      };

      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.onended = () => {
          if (isRecordingRef.value) {
            stopScreenRecording();
          }
        };
      }

      mediaRecorder.start(1000);
      isRecordingRef.value = true;
      recordStartTime = Date.now();
      recordTimerTextRef.value = '00:00';
      recordTimerInterval = setInterval(() => {
        const elapsedSec = Math.floor((Date.now() - recordStartTime) / 1000);
        const m = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
        const s = String(elapsedSec % 60).padStart(2, '0');
        recordTimerTextRef.value = `${m}:${s}`;
      }, 1000);

    } catch (err) {
      console.warn("录屏启动取消或失败:", err);
    }
  }

  function stopScreenRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecordingRef.value = false;
    if (recordTimerInterval) clearInterval(recordTimerInterval);
  }

  function toggleScreenRecording() {
    if (isRecordingRef.value) {
      stopScreenRecording();
    } else {
      startScreenRecording();
    }
  }

  function saveRecording() {
    if (!recordedChunks.length) return;
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    const d = new Date();
    const dateStr = `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}_${String(d.getHours()).padStart(2,'0')}${String(d.getMinutes()).padStart(2,'0')}`;
    a.download = `AI斗地主_解说录屏_${dateStr}.webm`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  }

  return {
    startScreenRecording,
    stopScreenRecording,
    toggleScreenRecording,
    saveRecording
  };
};
