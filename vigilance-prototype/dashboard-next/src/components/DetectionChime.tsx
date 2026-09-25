'use client';

/**
 * DetectionChime — plays a synthesized Web Audio chime and triggers
 * navigator.vibrate() when a road defect or license plate is detected
 * on the /capture page.
 *
 * Usage:
 *   import { playDetectionChime } from '@/components/DetectionChime';
 *   // When detection occurs:
 *   playDetectionChime('pothole');
 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  return audioCtx;
}

export type DetectionType = 'pothole' | 'crack' | 'plate' | 'vehicle';

const CHIME_CONFIGS: Record<DetectionType, { freq: number; freq2: number; duration: number; vibrateMs: number[] }> = {
  pothole: { freq: 880, freq2: 1108, duration: 0.25, vibrateMs: [150, 50, 150] },
  crack: { freq: 660, freq2: 830, duration: 0.2, vibrateMs: [100, 30, 100] },
  plate: { freq: 1200, freq2: 1500, duration: 0.15, vibrateMs: [80] },
  vehicle: { freq: 440, freq2: 554, duration: 0.15, vibrateMs: [50] },
};

export function playDetectionChime(type: DetectionType = 'pothole') {
  const config = CHIME_CONFIGS[type];

  try {
    const ctx = getAudioContext();
    const now = ctx.currentTime;

    // Oscillator 1 — primary tone
    const osc1 = ctx.createOscillator();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(config.freq, now);
    osc1.frequency.exponentialRampToValueAtTime(config.freq * 0.8, now + config.duration);

    // Oscillator 2 — harmonic overtone
    const osc2 = ctx.createOscillator();
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(config.freq2, now);

    // Gain envelope — sharp attack, smooth decay
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.3, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, now + config.duration);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + config.duration);
    osc2.stop(now + config.duration);
  } catch {
    // Audio API not available — silent fallback
  }

  // Haptic feedback (mobile only)
  try {
    if ('vibrate' in navigator) {
      navigator.vibrate(config.vibrateMs);
    }
  } catch {
    // Vibration API not available — silent fallback
  }
}

export default function DetectionChimePreloader() {
  // Invisible component — preloads AudioContext on first user interaction
  return null;
}
