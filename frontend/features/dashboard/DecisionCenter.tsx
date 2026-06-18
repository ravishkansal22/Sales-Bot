'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { OptimizationMode } from '../../types/api';
import { Cpu, RotateCcw, AlertCircle, Award, CheckCircle, Scale, DollarSign, Percent, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function DecisionCenter() {
  const { 
    optimizationMode, 
    setOptimizationMode, 
    optimizerResult, 
    isReplaying, 
    triggerReplay, 
    playbackStep 
  } = useNegotiationState();

  const modes: { id: OptimizationMode; label: string; desc: string; icon: React.ReactNode }[] = [
    { id: 'balanced', label: 'Balanced', desc: 'Equal risk/reward limits', icon: <Scale className="h-3.5 w-3.5" /> },
    { id: 'max_profit', label: 'Max Profit', desc: 'Optimize absolute ACV value', icon: <DollarSign className="h-3.5 w-3.5" /> },
    { id: 'max_margin', label: 'Max Margin', desc: 'Secure highest profit margin', icon: <Percent className="h-3.5 w-3.5" /> },
    { id: 'max_close_rate', label: 'Max Close', desc: 'Minimize immediate churn risks', icon: <ShieldCheck className="h-3.5 w-3.5" /> }
  ];

  const getWinnerColor = (id: string | undefined) => {
    if (!id) return 'text-cyan-glow border-cyan-glow/30';
    if (id.includes('discount')) return 'text-amber-400 border-amber-500/30';
    if (id.includes('hardline')) return 'text-rose-400 border-rose-500/30';
    if (id.includes('bundle')) return 'text-cyan-glow border-cyan-glow/30';
    return 'text-neon-purple border-neon-purple/30';
  };

  return (
    <div className="flex flex-col space-y-6 h-full">
      
      {/* Selector tabs and Playback trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        
        {/* Playback trigger */}
        <button
          onClick={triggerReplay}
          disabled={isReplaying}
          className={`relative flex items-center space-x-2 rounded-lg border px-4 py-2 font-mono text-xs font-bold transition-all ${
            isReplaying 
              ? 'bg-cyan-glow/10 border-cyan-glow/30 text-cyan-glow/60 cursor-not-allowed'
              : 'bg-cyan-glow/10 border-cyan-glow/30 text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.08)] hover:shadow-[0_0_15px_rgba(0,242,254,0.3)] hover:bg-cyan-glow/20'
          }`}
        >
          <RotateCcw className={`h-4.5 w-4.5 ${isReplaying ? 'animate-spin' : ''}`} />
          <span>REPLAY SIMULATION ENGINE</span>
        </button>

        {/* Optimizer Mode Toggles */}
        <div className="flex bg-black/60 rounded-lg border border-white/10 p-1">
          {modes.map((mode) => {
            const isActive = optimizationMode === mode.id;
            return (
              <button
                key={mode.id}
                disabled={isReplaying}
                onClick={() => setOptimizationMode(mode.id)}
                className={`relative flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-mono text-[10px] font-bold tracking-wider uppercase transition-all ${
                  isActive
                    ? 'bg-cyan-glow text-black shadow-[0_0_10px_rgba(0,242,254,0.2)]'
                    : 'text-white/60 hover:text-white hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed'
                }`}
              >
                {mode.icon}
                <span>{mode.label}</span>
              </button>
            );
          })}
        </div>

      </div>

      {/* Recommended Strategy Hero Card */}
      <div className="flex-1 min-h-[200px]">
        <AnimatePresence mode="wait">
          {!optimizerResult ? (
            <motion.div 
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="glass-panel rounded-xl p-6 flex flex-col justify-center items-center h-full border border-white/5 bg-white/[0.01]"
            >
              <Cpu className="h-8 w-8 text-cyan-glow/40 animate-spin mb-3" />
              <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
                {isReplaying ? 'OPTIMIZING CRITERIA MATRIX...' : 'OPTIMIZER ENGINE READY'}
              </span>
            </motion.div>
          ) : (
            <motion.div
              key={optimizerResult.winningStrategyId + optimizationMode}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ 
                opacity: 1, 
                scale: 1,
                boxShadow: '0 0 30px rgba(0, 242, 254, 0.12)' 
              }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.45 }}
              className={`glass-panel rounded-xl p-5.5 flex flex-col justify-between border ${getWinnerColor(optimizerResult?.winningStrategyId)}`}
            >
              <div className="flex flex-col space-y-4">
                
                {/* Winner Title */}
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center space-x-2">
                    <Award className="h-5 w-5 text-cyan-glow animate-bounce" />
                    <div>
                      <span className="font-mono text-[9px] text-white/40 leading-none block uppercase">
                        Optimizer Decision Center
                      </span>
                      <span className="font-mono text-sm font-bold text-white tracking-widest mt-1 block uppercase">
                        {optimizerResult.winningStrategyId === 's_discount' ? 'Discount Strategy' :
                         optimizerResult.winningStrategyId === 's_hardline' ? 'Hardline Strategy' :
                         optimizerResult.winningStrategyId === 's_bundle' ? 'Value Bundle Strategy' : 'Personalized Term'}
                      </span>
                    </div>
                  </div>
                  
                  {/* Neon Confidence Indicator Ring */}
                  <div className="flex items-center space-x-2.5">
                    <div className="flex flex-col text-right">
                      <span className="font-mono text-[8px] text-white/40 leading-none uppercase">Confidence</span>
                      <span className="font-mono text-[11px] font-bold text-cyan-glow mt-0.5">{(optimizerResult.confidenceScore * 100).toFixed(0)}%</span>
                    </div>
                    <div className="relative h-9 w-9">
                      <svg className="absolute inset-0 w-full h-full -rotate-90">
                        <circle cx="18" cy="18" r="14" className="text-white/5" strokeWidth="2.5" fill="none" />
                        <circle 
                          cx="18" cy="18" r="14" 
                          className="text-cyan-glow" 
                          strokeWidth="2.5" 
                          fill="none" 
                          strokeDasharray={2 * Math.PI * 14}
                          strokeDashoffset={2 * Math.PI * 14 - (optimizerResult.confidenceScore * 2 * Math.PI * 14)}
                          style={{ filter: 'drop-shadow(0px 0px 3px rgba(0, 242, 254, 0.4))' }}
                        />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Reasoning text */}
                <div>
                  <p className="font-mono text-[9px] text-white/40 uppercase leading-none mb-1.5">
                    OPTIMIZER REASONING MATRIX
                  </p>
                  <p className="text-xs text-white/80 font-sans leading-relaxed">
                    {optimizerResult.optimizerReasoning}
                  </p>
                </div>

                {/* Key Winning Factors */}
                <div className="space-y-2.5">
                  <p className="font-mono text-[9px] text-white/40 uppercase leading-none">
                    KEY DECISION FACTORS
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {optimizerResult.winningFactors.map((factor, i) => (
                      <div key={i} className="rounded border border-white/5 bg-black/40 p-3 flex space-x-2.5">
                        <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="text-[10.5px] text-white/70 font-sans leading-relaxed">
                          {factor}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

              </div>

            </motion.div>
          )}
        </AnimatePresence>
      </div>

    </div>
  );
}
