'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ShieldAlert, Radio, RefreshCw, Cpu, Activity, LayoutDashboard, BarChart3, Truck, ClipboardList, Search, Smartphone } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BackendConnectionStatus } from '@/hooks/useDashboardData';
import CitySelector from './CitySelector';

interface HeaderProps {
  activeVehicles?: number;
  isConnected?: boolean;
  backendAvailable?: boolean | null;
  backendStatus?: BackendConnectionStatus;
  onRefresh?: () => void;
  onTriggerDedup?: () => Promise<any>;
  onOpenCommandPalette?: () => void;
}

function LiveUTCClock() {
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toUTCString().slice(17, 25) + ' UTC');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="hidden lg:flex items-center gap-1 bg-white/[0.03] border border-white/10 px-2 py-1 rounded-lg text-[10.5px] text-slate-400 font-mono backdrop-blur-md">
      <Activity className="w-3 h-3 text-slate-500" />
      <span>{currentTime || 'SYNCING...'}</span>
    </div>
  );
}

export default function Header({
  activeVehicles = 5,
  isConnected = false,
  backendAvailable = null,
  backendStatus = 'unreachable',
  onRefresh,
  onTriggerDedup,
  onOpenCommandPalette,
}: HeaderProps) {
  const pathname = usePathname();
  const [isDeduping, setIsDeduping] = useState(false);

  // Global keyboard shortcut for Command Palette (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onOpenCommandPalette?.();
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [onOpenCommandPalette]);

  const handleDedupClick = async () => {
    if (!onTriggerDedup || isDeduping) return;
    setIsDeduping(true);
    try {
      await onTriggerDedup();
    } finally {
      setTimeout(() => setIsDeduping(false), 800);
    }
  };

  const navLinks = [
    { href: '/', label: 'Command Center', icon: LayoutDashboard },
    { href: '/analytics', label: 'Analytics', icon: BarChart3 },
    { href: '/fleet', label: 'Fleet Nodes', icon: Truck },
    { href: '/work-orders', label: 'Work Orders', icon: ClipboardList },
    { href: '/capture', label: 'Mobile Dashcam', icon: Smartphone },
  ];

  const isLive = backendAvailable === true || isConnected;
  const isColdStarting = backendStatus === 'cold-starting';

  return (
    <header className="h-14 bg-slate-950/60 backdrop-blur-2xl border-b border-white/10 px-3 lg:px-5 flex items-center justify-between z-30 select-none shrink-0 shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
      {/* Brand & Badge */}
      <div className="flex items-center gap-3.5">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-blue-600/80 backdrop-blur-md flex items-center justify-center text-white border border-blue-400/30 shadow-[0_0_15px_rgba(37,99,235,0.4)] group-hover:bg-blue-500 transition-all">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm tracking-wider text-slate-100 font-mono">
                VIGILANCE
              </span>
              <span className="bg-white/[0.06] backdrop-blur-md text-slate-300 text-[10px] font-mono px-1.5 py-0.5 rounded-md border border-white/10 font-semibold tracking-wide shadow-xs">
                SIH26124 • BEL
              </span>
            </div>
            <p className="text-[9.5px] text-slate-400 font-mono hidden sm:block">
              Urban Road Intelligence & Maintenance Dispatch
            </p>
          </div>
        </Link>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 ml-3 pl-3 border-l border-white/10">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all',
                  isActive
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-400/40 font-semibold shadow-[0_0_12px_rgba(59,130,246,0.25)]'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-white/[0.06] border border-transparent'
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Action / Telemetry Status Indicators */}
      <div className="flex items-center gap-2">
        {/* Command Palette Trigger Button */}
        {onOpenCommandPalette && (
          <button
            onClick={onOpenCommandPalette}
            className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-slate-100 border border-white/10 hover:border-white/20 transition-all text-xs font-mono backdrop-blur-md shadow-xs"
            title="Open Command Palette (Cmd+K)"
          >
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden xl:inline text-[11px]">Command Palette</span>
            <kbd className="hidden sm:inline text-[10px] bg-slate-900/80 text-slate-400 px-1 py-0.5 rounded border border-white/10 font-mono">
              ⌘K
            </kbd>
          </button>
        )}

        {/* Mobile Direct Dashcam Button */}
        <Link
          href="/capture"
          className="md:hidden flex items-center gap-1.5 bg-blue-600/90 hover:bg-blue-500 text-white text-[11px] font-mono font-bold px-2.5 py-1 rounded-lg border border-blue-400/30 shadow-[0_0_15px_rgba(37,99,235,0.3)] active:scale-95 transition"
        >
          <Smartphone className="w-3.5 h-3.5" />
          <span>Dashcam</span>
        </Link>

        {/* Live Backend / Demo Status Badge */}
        <div
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] font-mono border backdrop-blur-md transition-all shadow-xs',
            isLive
              ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
              : isColdStarting
              ? 'bg-amber-950/50 border-amber-500/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)] animate-pulse'
              : 'bg-rose-950/40 border-rose-500/40 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.2)]'
          )}
          title={
            isLive
              ? 'Connected to live FastAPI & PostGIS backend'
              : isColdStarting
              ? 'Backend is waking up from sleep (Render free tier cold-start)'
              : 'Backend unreachable — displaying fallback demo data'
          }
        >
          <span
            className={cn(
              'w-2 h-2 rounded-full',
              isLive
                ? 'bg-emerald-400 animate-pulse'
                : isColdStarting
                ? 'bg-amber-400 animate-ping'
                : 'bg-rose-400'
            )}
          />
          <span className="font-semibold">
            {isLive ? 'LIVE BACKEND' : isColdStarting ? 'WAKING BACKEND' : 'DEMO DATA'}
          </span>
        </div>

        {/* Active Fleet Node Count */}
        <div className="hidden sm:flex items-center gap-1.5 bg-white/[0.04] border border-white/10 px-2 py-1 rounded-lg text-xs text-slate-300 font-mono backdrop-blur-md">
          <Radio className="w-3.5 h-3.5 text-blue-400" />
          <span>{activeVehicles} Nodes</span>
        </div>

        {/* UTC Clock */}
        <LiveUTCClock />

        {/* City Selector Dropdown */}
        <CitySelector onCityChange={(city) => {
          console.log(`[VIGILANCE] Switched to ${city.display_name}`);
        }} />

        {/* Trigger Dedup Button */}
        {onTriggerDedup && (
          <button
            onClick={handleDedupClick}
            disabled={isDeduping}
            aria-busy={isDeduping}
            aria-label="Trigger manual 15-meter spatial deduplication"
            className="flex items-center gap-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 border border-white/10 hover:border-white/20 text-xs px-2.5 py-1 rounded-lg font-mono backdrop-blur-md transition-all disabled:opacity-50 active:scale-95"
            title="Trigger manual 15m DBSCAN spatial deduplication"
          >
            <Cpu className={cn('w-3.5 h-3.5 text-blue-400', isDeduping && 'animate-spin')} />
            <span className="hidden sm:inline">{isDeduping ? 'Deduping...' : 'Dedup'}</span>
          </button>
        )}

        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            aria-label="Refresh telemetry and cluster data"
            className="p-1 bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-slate-100 border border-white/10 hover:border-white/20 rounded-lg text-xs backdrop-blur-md transition active:scale-95"
            title="Refresh dashboard data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </header>

  );
}
