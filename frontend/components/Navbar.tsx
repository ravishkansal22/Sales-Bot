'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, ShieldAlert, Cpu, Database, Award, GitBranch } from 'lucide-react';
import { IS_DEMO_MODE } from '../services/api';
import { useNegotiationState } from '../hooks/useNegotiationState';

export default function Navbar() {
  const pathname = usePathname();
  const { isReplaying, playbackStep } = useNegotiationState();

  const getStepText = () => {
    switch (playbackStep) {
      case 1: return "Objection detected";
      case 2: return "Updating digital twin";
      case 3: return "Generating strategies";
      case 4: return "Running simulations";
      case 5: return "Evaluating financials";
      case 6: return "Optimizing decisions";
      default: return "Awaiting input";
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/10 bg-black/60 backdrop-blur-md px-6 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        
        {/* Left Brand Section */}
        <div className="flex items-center space-x-3">
          <Link href="/" className="flex items-center space-x-2.5 group">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-glow/30 bg-cyan-glow/5 transition-transform group-hover:scale-105">
              <div className="absolute inset-0 rounded-lg bg-cyan-glow/10 blur-sm opacity-50 group-hover:opacity-100 transition-opacity"></div>
              <Activity className="h-4.5 w-4.5 text-cyan-glow animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono text-lg font-bold tracking-wider text-white">
                  GHOST <span className="text-cyan-glow">NEGOTIATOR</span>
                </span>
                <span className="rounded bg-white/5 border border-white/10 px-1.5 py-0.5 font-mono text-[9px] text-white/50 tracking-widest uppercase">
                  v1.2.0
                </span>
              </div>
              <p className="font-mono text-[9px] text-white/40 tracking-widest uppercase">
                Revenue Intelligence Operating System
              </p>
            </div>
          </Link>
        </div>

        {/* Center System Status Telemetry */}
        {pathname.includes('/dashboard') && (
          <div className="hidden lg:flex items-center space-x-6 border-l border-white/10 pl-6">
            {/* Status Item 1: Simulation Engine */}
            <div className="flex items-center space-x-2">
              <div className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isReplaying ? 'bg-cyan-glow animate-ping' : 'bg-cyan-glow/65 animate-pulse'}`}></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-glow"></span>
              </div>
              <div>
                <p className="font-mono text-[9px] text-white/40 leading-none">SIMULATION ENGINE</p>
                <p className="font-mono text-[10px] font-bold text-white leading-none mt-1">
                  {isReplaying ? 'RUNNING' : 'ACTIVE'}
                </p>
              </div>
            </div>

            {/* Status Item 2: Digital Twin */}
            <div className="flex items-center space-x-2">
              <div className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isReplaying && playbackStep >= 2 ? 'bg-neon-purple animate-ping' : 'bg-neon-purple/65 animate-pulse'}`}></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-purple"></span>
              </div>
              <div>
                <p className="font-mono text-[9px] text-white/40 leading-none">DIGITAL TWIN</p>
                <p className="font-mono text-[10px] font-bold text-white leading-none mt-1">
                  {isReplaying && playbackStep < 2 ? 'SYNCING' : 'READY'}
                </p>
              </div>
            </div>

            {/* Status Item 3: Financial Evaluator */}
            <div className="flex items-center space-x-2">
              <div className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 bg-emerald-400/65 ${isReplaying && playbackStep >= 5 ? 'animate-ping' : 'animate-pulse'}`}></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
              </div>
              <div>
                <p className="font-mono text-[9px] text-white/40 leading-none">FINANCIAL EVALUATION</p>
                <p className="font-mono text-[10px] font-bold text-white leading-none mt-1">
                  {isReplaying && playbackStep < 5 ? 'PENDING' : 'ONLINE'}
                </p>
              </div>
            </div>

            {/* Status Item 4: Strategy Optimizer */}
            <div className="flex items-center space-x-2">
              <div className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 bg-indigo-500/65 ${isReplaying && playbackStep >= 6 ? 'animate-ping' : 'animate-pulse'}`}></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </div>
              <div>
                <p className="font-mono text-[9px] text-white/40 leading-none">STRATEGY OPTIMIZER</p>
                <p className="font-mono text-[10px] font-bold text-white leading-none mt-1">
                  {isReplaying && playbackStep < 6 ? 'CALCULATING' : 'OPTIMIZED'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Right Navigation & Mode Indicators */}
        <div className="flex items-center space-x-4">
          {isReplaying && (
            <div className="animate-pulse flex items-center space-x-1.5 rounded-full border border-cyan-glow/20 bg-cyan-glow/5 px-3 py-1 font-mono text-[10px] text-cyan-glow">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan-glow animate-ping"></span>
              <span>PLAYBACK: {getStepText()}</span>
            </div>
          )}

          {IS_DEMO_MODE ? (
            <div className="flex items-center space-x-1 rounded-md border border-amber-500/30 bg-amber-500/5 px-2.5 py-0.5 font-mono text-[10px] text-amber-400">
              <ShieldAlert className="h-3 w-3" />
              <span>DEMO MODE (MOCK)</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-2.5 py-0.5 font-mono text-[10px] text-emerald-400">
              <Activity className="h-3 w-3" />
              <span>PRODUCTION (FASTAPI)</span>
            </div>
          )}

          {pathname === '/dashboard' ? (
            <Link 
              href="/workspace"
              className="rounded-lg border border-cyan-glow/30 bg-cyan-glow/5 px-3.5 py-1.5 font-mono text-xs text-cyan-glow hover:text-white hover:bg-cyan-glow/20 transition-all"
            >
              RETURN TO WORKSPACE
            </Link>
          ) : pathname === '/workspace' ? (
            <Link 
              href="/dashboard"
              className="relative rounded-lg border border-cyan-glow/30 bg-cyan-glow/15 px-3.5 py-1.5 font-mono text-xs text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.15)] hover:shadow-[0_0_15px_rgba(0,242,254,0.35)] hover:bg-cyan-glow/30 transition-all"
            >
              VIEW AI ANALYSIS
            </Link>
          ) : (
            <Link 
              href="/workspace"
              className="relative rounded-lg border border-cyan-glow/30 bg-cyan-glow/10 px-3.5 py-1.5 font-mono text-xs text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.1)] hover:shadow-[0_0_15px_rgba(0,242,254,0.3)] hover:bg-cyan-glow/25 transition-all"
            >
              ENTER WORKSPACE
            </Link>
          )}
        </div>

      </div>
    </header>
  );
}
