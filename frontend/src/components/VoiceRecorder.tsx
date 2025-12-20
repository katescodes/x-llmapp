/**
 * 实时语音录音组件
 * 支持：边录边转写、波形动画、实时显示转写文字
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import '../styles/voice-recorder.css';

interface VoiceRecorderProps {
  onComplete: (recording: RecordingResult) => void;
  onCancel?: () => void;
}

export interface RecordingResult {
  recording_id: string;
  full_transcript: string;
  duration: number;
  word_count: number;
}

const VoiceRecorder: React.FC<VoiceRecorderProps> = ({ onComplete, onCancel }) => {
  const { token } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [duration, setDuration] = useState(0);
  const [transcript, setTranscript] = useState('');
  const [status, setStatus] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // API 基础URL
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const wsBaseUrl = apiBaseUrl.replace('http', 'ws');

  // 计时器
  useEffect(() => {
    if (isRecording && !isPaused) {
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording, isPaused]);

  // 格式化时间
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 音量可视化
  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current || !isRecording) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
    setAudioLevel(average / 255);

    if (isRecording) {
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    }
  }, [isRecording]);

  // 开始录音
  const startRecording = async () => {
    if (!token) {
      setError('未登录，无法使用录音功能');
      return;
    }

    // 检查浏览器是否支持录音
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('您的浏览器不支持录音功能，或需要使用 HTTPS 访问。请使用 Chrome/Edge/Firefox 最新版本，或联系管理员配置 HTTPS');
      return;
    }

    try {
      setError('');
      setStatus('正在获取麦克风权限...');

      // 获取麦克风
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      setStatus('正在连接转写服务...');

      // 建立 WebSocket 连接
      const ws = new WebSocket(`${wsBaseUrl}/ws/asr?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('');
        
        // 发送开始命令
        ws.send(
          JSON.stringify({
            action: 'start',
            config: {
              language: 'zh',
              enable_timestamps: false,
            },
          })
        );

        // 设置音频上下文（用于可视化）
        const audioContext = new AudioContext();
        audioContextRef.current = audioContext;
        const analyser = audioContext.createAnalyser();
        analyserRef.current = analyser;
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        updateAudioLevel();

        // 开始录音 - 自动选择移动端支持的格式
        let mimeType = 'audio/webm;codecs=opus';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          // iOS Safari 回退到 mp4
          mimeType = 'audio/mp4';
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            // 最终回退到默认格式
            mimeType = '';
          }
        }
        
        const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(event.data);
          }
        };

        mediaRecorder.start(250); // 每 250ms 发送一次
        setIsRecording(true);
        setStatus('');
        setDuration(0);
        setTranscript('');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'final') {
            // 最终结果
            onComplete({
              recording_id: data.recording_id,
              full_transcript: data.full_transcript,
              duration: data.duration,
              word_count: data.word_count,
            });
            cleanup();
          } else if (data.type === 'error') {
            setError(data.message);
          } else if (data.type === 'status') {
            if (data.message.includes('Processing')) {
              setStatus('正在转写音频...');
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('连接失败，请检查网络或服务状态');
        cleanup();
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        cleanup();
      };
    } catch (err: any) {
      console.error('Failed to start recording:', err);
      setError(err.message || '无法访问麦克风，请检查浏览器权限');
      cleanup();
    }
  };

  // 停止录音
  const stopRecording = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
      setStatus('正在处理录音...');
    }
  };

  // 暂停/恢复录音
  const togglePause = () => {
    if (mediaRecorderRef.current) {
      if (isPaused) {
        mediaRecorderRef.current.resume();
        setIsPaused(false);
      } else {
        mediaRecorderRef.current.pause();
        setIsPaused(true);
      }
    }
  };

  // 取消录音
  const cancelRecording = () => {
    cleanup();
    if (onCancel) {
      onCancel();
    }
  };

  // 清理资源
  const cleanup = () => {
    // 停止媒体录制器
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
    }

    // 关闭 WebSocket
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    // 关闭音频上下文
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // 取消动画帧
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    setIsRecording(false);
    setIsPaused(false);
    setStatus('');
    setAudioLevel(0);
  };

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  return (
    <div className="voice-recorder">
      {!isRecording ? (
        <div className="recorder-idle">
          <button className="record-btn" onClick={startRecording} disabled={!!error}>
            <span className="record-icon">🎤</span>
            <span>开始录音</span>
          </button>
          {error && <div className="recorder-error">⚠️ {error}</div>}
          {status && <div className="recorder-status">{status}</div>}
        </div>
      ) : (
        <div className="recorder-active">
          {/* 波形动画 */}
          <div className="waveform">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="wave-bar"
                style={{
                  height: `${Math.max(20, audioLevel * 100 * (1 + Math.sin(Date.now() / 200 + i)))}%`,
                }}
              />
            ))}
          </div>

          {/* 时长显示 */}
          <div className="duration">
            <span className={`recording-indicator ${isPaused ? 'paused' : ''}`}>
              {isPaused ? '⏸️' : '🔴'}
            </span>
            {formatTime(duration)}
          </div>

          {/* 状态提示 */}
          {status && <div className="recorder-status">{status}</div>}

          {/* 控制按钮 */}
          <div className="controls">
            <button onClick={togglePause} className="control-btn pause">
              {isPaused ? '▶️ 继续' : '⏸️ 暂停'}
            </button>
            <button onClick={stopRecording} className="control-btn stop">
              ✅ 完成
            </button>
            <button onClick={cancelRecording} className="control-btn cancel">
              ❌ 取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default VoiceRecorder;

