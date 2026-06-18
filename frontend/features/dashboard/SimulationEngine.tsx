'use client';

import React, { useState, useEffect } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { SimulationOutput, SimulationRollout } from '../../types/api';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, TrendingUp, AlertTriangle, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';

export default function SimulationEngine() {
  const { 
    simulations, 
    selectedStrategyId, 
    setSelectedStrategyId, 
    isReplaying, 
    playbackStep 
  } = useNegotiationState();

  const [simulatedCount, setSimulatedCount] = useState(0);

  // Animate the simulated futures counter
  useEffect(() => {
    if (isReplaying) {
      if (playbackStep < 4) {
        setSimulatedCount(0);
      } else {
        // Tick up from 0 to 24 quickly
        let start = 0;
        const end = 24;
        const duration = 1200;
        const increment = Math.ceil(end / (duration / 50));
        const timer = setInterval(() => {
          start += increment;
          if (start >= end) {
            setSimulatedCount(end);
            clearInterval(timer);
          } else {
            setSimulatedCount(start);
          }
        }, 50);
        return () => clearInterval(timer);
      }
    } else {
      setSimulatedCount(24);
    }
  }, [isReplaying, playbackStep]);

  const getStrategyColorClasses = (id: string) => {
    switch (id) {
      case 's_discount':
        return {
          glow: 'hover:shadow-[0_0_20px_rgba(245,158,11,0.25)] hover:border-amber-500/50',
          border: 'border-amber-500/20',
          text: 'text-amber-400',
          bg: 'bg-amber-500/5',
          progress: 'bg-amber-500'
        };
      case 's_hardline':
        return {
          glow: 'hover:shadow-[0_0_20px_rgba(244,63,94,0.25)] hover:border-rose-500/50',
          border: 'border-rose-500/20',
          text: 'text-rose-400',
          bg: 'bg-rose-500/5',
          progress: 'bg-rose-500'
        };
      case 's_bundle':
        return {
          glow: 'hover:shadow-[0_0_20px_rgba(0,242,254,0.25)] hover:border-cyan-glow/50',
          border: 'border-cyan-glow/20',
          text: 'text-cyan-glow',
          bg: 'bg-cyan-glow/5',
          progress: 'bg-cyan-glow'
        };
      case 's_personalized':
        return {
          glow: 'hover:shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:border-neon-purple/50',
          border: 'border-neon-purple/20',
          text: 'text-neon-purple',
          bg: 'bg-neon-purple/5',
          progress: 'bg-neon-purple'
        };
      default:
        return {
          glow: 'hover:shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:border-white/30',
          border: 'border-white/10',
          text: 'text-white',
          bg: 'bg-white/5',
          progress: 'bg-white'
        };
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  };

  return (
    <div className="flex flex-col space-y-5 h-full">
      
      {/* Header section with simulated count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Play className="h-4 w-4 text-cyan-glow animate-pulse" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Future Simulation Engine
          </span>
        </div>
        <div className="flex items-center space-x-2 rounded border border-cyan-glow/20 bg-cyan-glow/5 px-2.5 py-1 font-mono text-xs text-cyan-glow">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full rounded-full bg-cyan-glow opacity-75 animate-ping"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-glow"></span>
          </span>
          <span className="font-bold tracking-wider">{simulatedCount}</span>
          <span className="text-white/40">FUTURES EVALUATED</span>
        </div>
      </div>

      {/* Strategies list Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
        {simulations.length === 0 ? (
          <div className="col-span-2 flex flex-col items-center justify-center p-8 border border-white/5 rounded-xl bg-white/[0.01] min-h-[200px]">
            <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
            <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
              GENERATING DECISION MATRIX...
            </span>
          </div>
        ) : (
          simulations.map((strat) => {
            const styles = getStrategyColorClasses(strat.id);
            const isSelected = selectedStrategyId === strat.id;

            return (
              <div
                key={strat.id}
                className={`glass-panel rounded-xl p-4.5 flex flex-col justify-between cursor-pointer border ${styles.border} ${styles.glow} ${
                  isSelected ? 'border-cyan-glow/50 bg-cyan-glow/[0.02] shadow-[0_0_15px_rgba(0,242,254,0.08)]' : ''
                }`}
                onClick={() => setSelectedStrategyId(isSelected ? null : strat.id)}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`font-mono text-[11px] font-bold tracking-wider uppercase ${styles.text}`}>
                      {strat.name}
                    </span>
                    <span className="rounded bg-white/5 border border-white/10 px-2 py-0.5 font-mono text-[9px] text-white/60">
                      Conf: {(strat.confidenceScore * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-[11px] text-white/60 font-sans leading-relaxed mb-4">
                    {strat.description}
                  </p>
                </div>

                <div className="space-y-3">
                  {/* Metric 1: Close Probability */}
                  <div className="space-y-1">
                    <div className="flex justify-between font-mono text-[9px] text-white/50 leading-none">
                      <span>CLOSE PROBABILITY</span>
                      <span className="font-bold text-white">{(strat.closeProbability * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${strat.closeProbability * 100}%` }}
                        transition={{ duration: 0.8 }}
                        className={`h-full ${styles.progress}`}
                      />
                    </div>
                  </div>

                  {/* Metric 2: Margin Retention */}
                  <div className="space-y-1">
                    <div className="flex justify-between font-mono text-[9px] text-white/50 leading-none">
                      <span>MARGIN RETENTION</span>
                      <span className="font-bold text-white">{(strat.marginRetention * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${strat.marginRetention * 100}%` }}
                        transition={{ duration: 0.8 }}
                        className={`h-full ${styles.progress}`}
                      />
                    </div>
                  </div>

                  {/* Bottom details: Profit & Risk */}
                  <div className="flex justify-between items-center pt-2 border-t border-white/5 font-mono text-[10px]">
                    <div className="flex flex-col">
                      <span className="text-white/40 text-[8px] leading-none">EXPECTED PROFIT</span>
                      <span className="font-bold text-white mt-0.5">{formatCurrency(strat.expectedProfit)}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-white/40 text-[8px] leading-none">RISK PROFILE</span>
                      <span className={`font-bold mt-0.5 ${
                        strat.riskScore >= 70 ? 'text-rose-400' :
                        strat.riskScore >= 40 ? 'text-amber-400' : 'text-emerald-400'
                      }`}>
                        {strat.riskScore}/100
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Rollout Explorer (Collapsible View) */}
      <AnimatePresence>
        {selectedStrategyId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden border border-white/10 rounded-xl bg-white/[0.01] glass-panel"
          >
            <div className="p-4 border-b border-white/10 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-glow animate-pulse"></span>
                <span className="font-mono text-[11px] font-bold text-white/80 uppercase">
                  Rollout Path Telemetry — {simulations.find(s => s.id === selectedStrategyId)?.name}
                </span>
              </div>
              <button 
                onClick={() => setSelectedStrategyId(null)}
                className="font-mono text-[9px] text-white/40 hover:text-white uppercase transition-colors"
              >
                Close Rollouts
              </button>
            </div>
            
            <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              {simulations.find(s => s.id === selectedStrategyId)?.rollouts.map((roll, idx) => (
                <motion.div
                  key={roll.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="rounded-lg border border-white/5 bg-black/40 p-4 flex flex-col justify-between space-y-4"
                >
                  <div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2 mb-3">
                      <span className="font-mono text-[10px] font-bold text-white/80">
                        {roll.stepName}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 font-mono text-[8px] font-bold ${
                        roll.risk === 'HIGH' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                        roll.risk === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                        'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}>
                        {roll.risk} RISK
                      </span>
                    </div>

                    <div className="space-y-3 text-[11px]">
                      <div>
                        <p className="font-mono text-[9px] text-white/40 leading-none">CUSTOMER REACTION</p>
                        <p className="text-white/80 mt-1 font-sans leading-relaxed">{roll.customerReaction}</p>
                      </div>
                      
                      <div>
                        <p className="font-mono text-[9px] text-white/40 leading-none">TELEMETRY EVENTS</p>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {roll.timelineEvents.map((evt, i) => (
                            <span key={i} className="rounded bg-white/5 border border-white/10 px-1.5 py-0.5 font-mono text-[8px] text-white/50">
                              {evt}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-white/5 pt-3 mt-1 bg-white/[0.01] -mx-4 -mb-4 p-4 rounded-b-lg">
                    <p className="font-mono text-[9px] text-cyan-glow leading-none uppercase">OUTCOME PROFILE</p>
                    <p className="text-white font-sans text-[11px] leading-relaxed mt-1">{roll.outcome}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
