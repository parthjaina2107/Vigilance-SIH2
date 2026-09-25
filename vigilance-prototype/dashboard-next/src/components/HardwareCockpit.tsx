'use client';

import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Wifi, Activity, HardDrive, Gauge, ChevronDown, ChevronUp } from 'lucide-react';

interface CockpitMetric {
  label: string;
  value: string;
  subtext: string;
  icon: React.ReactNode;
  accentColor: string;
  gaugePercent: number;
}

export default function HardwareCockpit() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [gForce, setGForce] = useState(0.0);
  const [gForceActive, setGForceActive] = useState(false);

  // Simulated G-force from accelerometer (real data comes via DeviceMotion in /capture)
  useEffect(() => {
    const interval = setInterval(() => {
      // Simulate accelerometer data — in production, this reads DeviceMotionEvent
      const simulated = 0.5 + Math.random() * 4.5;
      setGForce(parseFloat(simulated.toFixed(2)));
      setGForceActive(simulated > 3.5);
    }, 800);
    return () => clearInterval(interval);
  }, []);

  const metrics: CockpitMetric[] = [
    {
      label: 'Model Size (INT8)',
      value: '3.2 MB',
      subtext: 'vs 12.2 MB FP32 → 72.6% compression',
      icon: <HardDrive className="w-5 h-5" />,
      accentColor: 'cyan',
      gaugePercent: 26.2, // 3.2/12.2 * 100
    },
    {
      label: 'Mean Latency (INT8)',
      value: '28.4 ms',
      subtext: 'vs 64.2 ms FP32 → 2.26× speedup',
      icon: <Zap className="w-5 h-5" />,
      accentColor: 'green',
      gaugePercent: 44.2, // 28.4/64.2 * 100
    },
    {
      label: 'Bandwidth Saved',
      value: '99.8%',
      subtext: '200B MQTT vs 5 Mbps raw video',
      icon: <Wifi className="w-5 h-5" />,
      accentColor: 'amber',
      gaugePercent: 99.8,
    },
    {
      label: 'Edge Hardware Cost',
      value: '₹2,800',
      subtext: 'Raspberry Pi 4B + Camera Module v3',
      icon: <Cpu className="w-5 h-5" />,
      accentColor: 'red',
      gaugePercent: 9.3, // 2800/30000 * 100 (vs typical server)
    },
  ];

  const accentStyles: Record<string, { border: string; text: string; bg: string; glow: string; fill: string }> = {
    cyan: {
      border: 'border-cyan-500/30',
      text: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
      glow: 'shadow-[0_0_20px_rgba(34,211,238,0.15)]',
      fill: 'from-cyan-600 to-cyan-400',
    },
    green: {
      border: 'border-emerald-500/30',
      text: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      glow: 'shadow-[0_0_20px_rgba(74,222,128,0.15)]',
      fill: 'from-emerald-600 to-emerald-400',
    },
    amber: {
      border: 'border-amber-500/30',
      text: 'text-amber-400',
      bg: 'bg-amber-500/10',
      glow: 'shadow-[0_0_20px_rgba(251,191,36,0.15)]',
      fill: 'from-amber-600 to-amber-400',
    },
    red: {
      border: 'border-rose-500/30',
      text: 'text-rose-400',
      bg: 'bg-rose-500/10',
      glow: 'shadow-[0_0_20px_rgba(248,113,113,0.15)]',
      fill: 'from-rose-600 to-rose-400',
    },
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden animate-slide-up">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-5 py-3.5 bg-slate-900/60 border-b border-white/[0.06] hover:bg-slate-900/80 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center border border-cyan-500/30">
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-bold text-slate-100 font-mono tracking-wide">
              EDGE AI HARDWARE COCKPIT
            </h3>
            <p className="text-[10px] text-slate-500 font-mono">
              INT8 Quantized • Sub-₹3,000 Hardware • MQTT Telemetry
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Live G-force indicator */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border backdrop-blur-md transition-all ${
            gForceActive
              ? 'bg-rose-950/50 border-rose-500/40 text-rose-300 shadow-[0_0_15px_rgba(248,113,113,0.3)] animate-pulse'
              : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-400'
          }`}>
            <Activity className="w-3 h-3" />
            <span>{gForce} m/s²</span>
            <span className="font-semibold">{gForceActive ? 'BUMP' : 'IDLE'}</span>
          </div>
          {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="p-4">
          {/* Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {metrics.map((m, idx) => {
              const style = accentStyles[m.accentColor];
              return (
                <div
                  key={idx}
                  className={`glass-card glass-card-hover rounded-xl p-4 ${style.border} ${style.glow} cursor-default`}
                >
                  {/* Icon + Label */}
                  <div className="flex items-center gap-2.5 mb-3">
                    <div className={`w-9 h-9 rounded-lg ${style.bg} flex items-center justify-center ${style.text} border ${style.border}`}>
                      {m.icon}
                    </div>
                    <span className="text-[11px] font-mono text-slate-400 leading-tight">
                      {m.label}
                    </span>
                  </div>

                  {/* Value */}
                  <div className={`text-2xl font-extrabold font-mono ${style.text} tracking-tight mb-1`}>
                    {m.value}
                  </div>

                  {/* Subtext */}
                  <p className="text-[10px] text-slate-500 font-mono mb-3 leading-relaxed">
                    {m.subtext}
                  </p>

                  {/* Gauge Bar */}
                  <div className="h-2 rounded-full bg-slate-800/60 overflow-hidden">
                    <div
                      className={`h-full rounded-full bg-gradient-to-r ${style.fill} transition-all duration-[1500ms] ease-out`}
                      style={{ width: `${m.gaugePercent}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-[9px] text-slate-600 font-mono">0</span>
                    <span className={`text-[9px] font-mono font-semibold ${style.text}`}>
                      {m.gaugePercent.toFixed(1)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* G-Force Vibration Gauge */}
          <div className="mt-4 glass-card rounded-xl p-4 border-cyan-500/20">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-mono font-semibold text-slate-300">
                  ACCELEROMETER VIBRATION GAUGE
                </span>
              </div>
              <span className={`text-xs font-mono font-bold ${gForceActive ? 'text-rose-400' : 'text-emerald-400'}`}>
                THRESHOLD: 3.5 m/s²
              </span>
            </div>
            <div className="flex items-end gap-1 h-16">
              {Array.from({ length: 24 }).map((_, i) => {
                const barHeight = 20 + Math.random() * (gForceActive ? 80 : 40);
                const isHot = barHeight > 60;
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-t-sm transition-all duration-300 ${
                      isHot
                        ? 'bg-gradient-to-t from-rose-600 to-amber-400 shadow-[0_0_8px_rgba(248,113,113,0.4)]'
                        : 'bg-gradient-to-t from-cyan-700 to-cyan-400'
                    }`}
                    style={{
                      height: `${barHeight}%`,
                      animationDelay: `${i * 50}ms`,
                    }}
                  />
                );
              })}
            </div>
            <div className="flex justify-between mt-2">
              <span className="text-[9px] text-slate-600 font-mono">0 Hz</span>
              <span className={`text-[10px] font-mono font-bold ${gForceActive ? 'text-rose-400 animate-pulse' : 'text-cyan-400'}`}>
                {gForceActive ? '⚠ ROAD DEFECT ZONE — CAPTURING' : '● MONITORING — SMOOTH ROAD'}
              </span>
              <span className="text-[9px] text-slate-600 font-mono">50 Hz</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
