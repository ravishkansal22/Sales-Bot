'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { motion } from 'framer-motion';
import { Network, Database, ChevronRight, BarChart4, Cpu, Award } from 'lucide-react';

export default function SimulationGraph() {
  const { 
    selectedStrategyId, 
    optimizationMode, 
    optimizerResult, 
    isReplaying, 
    playbackStep 
  } = useNegotiationState();

  const activeWinner = optimizerResult?.winningStrategyId || 's_bundle';

  // Y positions for middle strategy nodes
  const strategies = [
    { id: 's_discount', label: 'Discount', y: 40, color: 'text-amber-400', glow: 'rgba(245, 158, 11, 0.4)' },
    { id: 's_hardline', label: 'Hardline', y: 110, color: 'text-rose-500', glow: 'rgba(244, 63, 94, 0.4)' },
    { id: 's_bundle', label: 'Bundle', y: 180, color: 'text-cyan-glow', glow: 'rgba(0, 242, 254, 0.4)' },
    { id: 's_personalized', label: 'Personalized', y: 250, color: 'text-neon-purple', glow: 'rgba(139, 92, 246, 0.4)' }
  ];

  // Helper to determine if path/node is highlighted
  const isInputActive = !isReplaying || playbackStep >= 1;
  const isStrategyActive = (id: string) => {
    if (isReplaying) {
      if (playbackStep < 3) return false;
      if (playbackStep === 3) return id === 's_discount' || id === 's_hardline'; // load first two
      return true; // steps 4, 5, 6
    }
    return true;
  };
  const isSelectedPath = (id: string) => {
    if (isReplaying && playbackStep < 4) return false;
    return id === selectedStrategyId;
  };
  const isFinancialsActive = !isReplaying || playbackStep >= 5;
  const isOptimizerActive = !isReplaying || playbackStep >= 6;

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[350px]">
      <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div className="flex items-center space-x-2">
          <Network className="h-4 w-4 text-cyan-glow animate-pulse" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Simulation Neural Routing Matrix
          </span>
        </div>
        <div className="flex items-center space-x-1 font-mono text-[9px] text-white/40">
          <span>OPTIMIZER MODE:</span>
          <span className="text-cyan-glow uppercase font-bold">{optimizationMode.replace('_', ' ')}</span>
        </div>
      </div>

      <div className="flex-1 relative min-h-[280px] w-full overflow-hidden flex items-center justify-center bg-black/10 rounded-lg border border-white/5">
        
        {/* SVG Drawing Canvas */}
        <svg 
          viewBox="0 0 960 300" 
          className="absolute inset-0 w-full h-full p-2 select-none"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Defs for gradients & filters */}
          <defs>
            <filter id="glow-filter" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            
            <linearGradient id="gradient-blue" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0066ff" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#00f2fe" stopOpacity="0.8" />
            </linearGradient>

            <linearGradient id="gradient-purple" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.8" />
            </linearGradient>
          </defs>

          {/* Paths from Input Node to Strategy Nodes */}
          {strategies.map((strat) => {
            const active = isStrategyActive(strat.id);
            const selected = isSelectedPath(strat.id);
            
            return (
              <g key={`path-in-${strat.id}`}>
                {/* Background Shadow line */}
                <path
                  d={`M 75 150 Q 180 ${strat.y} 280 ${strat.y}`}
                  fill="none"
                  stroke={selected ? '#00f2fe' : '#ffffff'}
                  strokeWidth={selected ? 2.5 : 1}
                  strokeOpacity={selected ? 0.8 : active ? 0.15 : 0.03}
                  className="transition-all duration-500"
                  filter={selected ? "url(#glow-filter)" : ""}
                />
                
                {/* Flow particles along active/selected paths */}
                {active && (
                  <path
                    d={`M 75 150 Q 180 ${strat.y} 280 ${strat.y}`}
                    fill="none"
                    stroke={selected ? 'url(#gradient-blue)' : 'rgba(255,255,255,0.4)'}
                    strokeWidth={selected ? 3 : 1.5}
                    strokeDasharray={selected ? "15, 60" : "8, 30"}
                    className="animate-flow-dash"
                    style={{
                      animation: 'flow 4s linear infinite',
                      strokeDashoffset: selected ? 80 : 150
                    }}
                  />
                )}
              </g>
            );
          })}

          {/* Paths from Strategy Nodes to Financial Evaluator */}
          {strategies.map((strat) => {
            const active = isStrategyActive(strat.id) && isFinancialsActive;
            const selected = isSelectedPath(strat.id) && isFinancialsActive;
            
            return (
              <g key={`path-out-${strat.id}`}>
                <path
                  d={`M 390 ${strat.y} Q 480 ${strat.y} 570 150`}
                  fill="none"
                  stroke={selected ? '#00f2fe' : '#ffffff'}
                  strokeWidth={selected ? 2.5 : 1}
                  strokeOpacity={selected ? 0.8 : active ? 0.15 : 0.03}
                  className="transition-all duration-500"
                  filter={selected ? "url(#glow-filter)" : ""}
                />
                
                {active && (
                  <path
                    d={`M 390 ${strat.y} Q 480 ${strat.y} 570 150`}
                    fill="none"
                    stroke={selected ? 'url(#gradient-blue)' : 'rgba(255,255,255,0.4)'}
                    strokeWidth={selected ? 3 : 1.5}
                    strokeDasharray={selected ? "15, 60" : "8, 30"}
                    style={{
                      animation: 'flow 4s linear infinite',
                      strokeDashoffset: selected ? 40 : 100
                    }}
                  />
                )}
              </g>
            );
          })}

          {/* Path from Financials to Optimizer */}
          <path
            d="M 670 150 L 760 150"
            fill="none"
            stroke={isOptimizerActive ? '#00f2fe' : '#ffffff'}
            strokeWidth={isOptimizerActive ? 2.5 : 1}
            strokeOpacity={isOptimizerActive ? 0.8 : 0.1}
            className="transition-all duration-500"
            filter={isOptimizerActive ? "url(#glow-filter)" : ""}
          />
          {isOptimizerActive && (
            <line
              x1="670" y1="150" x2="760" y2="150"
              stroke="url(#gradient-purple)"
              strokeWidth="3"
              strokeDasharray="10, 40"
              style={{ animation: 'flow 2s linear infinite' }}
            />
          )}

          {/* Path from Optimizer to Winner */}
          <path
            d="M 840 150 L 920 150"
            fill="none"
            stroke={isOptimizerActive ? '#8b5cf6' : '#ffffff'}
            strokeWidth={isOptimizerActive ? 3 : 1}
            strokeOpacity={isOptimizerActive ? 0.9 : 0.1}
            className="transition-all duration-500"
            filter={isOptimizerActive ? "url(#glow-filter)" : ""}
          />

          {/* 1. INPUT NODE (Customer message / Digital twin profile) */}
          <foreignObject x="10" y="105" width="130" height="90">
            <motion.div 
              animate={{ 
                borderColor: isInputActive ? 'rgba(0, 242, 254, 0.4)' : 'rgba(255,255,255,0.1)',
                boxShadow: isInputActive ? '0 0 15px rgba(0, 242, 254, 0.15)' : 'none'
              }}
              className="w-[110px] h-[90px] rounded-lg border bg-black/80 flex flex-col items-center justify-center p-2 text-center"
            >
              <Database className={`h-5 w-5 mb-1 ${isInputActive ? 'text-cyan-glow animate-pulse' : 'text-white/30'}`} />
              <span className="font-mono text-[9px] font-bold text-white/80">CUSTOMER TWIN</span>
              <span className="font-mono text-[8px] text-white/40 mt-0.5 leading-none">Price Sensitivity: 85</span>
            </motion.div>
          </foreignObject>

          {/* 2. STRATEGY NODES */}
          {strategies.map((strat) => {
            const active = isStrategyActive(strat.id);
            const selected = isSelectedPath(strat.id);
            
            return (
              <foreignObject key={strat.id} x="260" y={strat.y - 25} width="150" height="50">
                <motion.div
                  animate={{
                    borderColor: selected 
                      ? 'rgba(0, 242, 254, 0.6)' 
                      : active 
                        ? 'rgba(255,255,255,0.2)' 
                        : 'rgba(255,255,255,0.05)',
                    backgroundColor: selected ? 'rgba(0, 102, 255, 0.08)' : 'rgba(9, 11, 20, 0.85)',
                    boxShadow: selected ? `0 0 15px ${strat.glow}` : 'none'
                  }}
                  className="w-[130px] h-[46px] rounded-lg border flex items-center p-2.5 space-x-2 cursor-pointer hover:border-white/40 transition-colors"
                >
                  <div className={`h-2.5 w-2.5 rounded-full ${active ? strat.color : 'bg-white/20'} ${selected ? 'animate-ping' : ''}`} />
                  <div className="flex flex-col text-left overflow-hidden">
                    <span className="font-mono text-[10px] font-bold text-white leading-tight truncate">{strat.label}</span>
                    <span className="font-mono text-[7px] text-white/40 leading-none">
                      {strat.id === 's_discount' ? '92% Close' : 
                       strat.id === 's_hardline' ? '25% Close' :
                       strat.id === 's_bundle' ? '88% Close' : '80% Close'}
                    </span>
                  </div>
                </motion.div>
              </foreignObject>
            );
          })}

          {/* 3. FINANCIAL EVALUATOR NODE */}
          <foreignObject x="550" y="110" width="140" height="80">
            <motion.div 
              animate={{ 
                borderColor: isFinancialsActive ? 'rgba(139, 92, 246, 0.4)' : 'rgba(255,255,255,0.1)',
                boxShadow: isFinancialsActive ? '0 0 15px rgba(139, 92, 246, 0.15)' : 'none'
              }}
              className="w-[120px] h-[80px] rounded-lg border bg-black/80 flex flex-col items-center justify-center p-2 text-center"
            >
              <BarChart4 className={`h-5 w-5 mb-1 ${isFinancialsActive ? 'text-neon-purple' : 'text-white/30'}`} />
              <span className="font-mono text-[9px] font-bold text-white/80">FINANCIAL AUDIT</span>
              <span className="font-mono text-[8px] text-emerald-400 mt-0.5 leading-none">ROI Verified</span>
            </motion.div>
          </foreignObject>

          {/* 4. OPTIMIZER NODE */}
          <foreignObject x="720" y="110" width="140" height="80">
            <motion.div 
              animate={{ 
                borderColor: isOptimizerActive ? 'rgba(0, 242, 254, 0.5)' : 'rgba(255,255,255,0.1)',
                boxShadow: isOptimizerActive ? '0 0 15px rgba(0, 242, 254, 0.2)' : 'none'
              }}
              className="w-[120px] h-[80px] rounded-lg border bg-black/80 flex flex-col items-center justify-center p-2 text-center"
            >
              <Cpu className={`h-5 w-5 mb-1 ${isOptimizerActive ? 'text-cyan-glow' : 'text-white/30'} ${isReplaying && playbackStep === 6 ? 'animate-spin' : ''}`} />
              <span className="font-mono text-[9px] font-bold text-white/80 font-mono">OPTIMIZER</span>
              <span className="font-mono text-[8px] text-white/40 mt-0.5 leading-none">Mode: {optimizationMode}</span>
            </motion.div>
          </foreignObject>

          {/* 5. RECOMMENDED ACTION / WINNER */}
          <foreignObject x="890" y="110" width="70" height="80">
            <motion.div 
              animate={{ 
                borderColor: isOptimizerActive ? 'rgba(139, 92, 246, 0.6)' : 'rgba(255,255,255,0.05)',
                boxShadow: isOptimizerActive ? '0 0 15px rgba(139, 92, 246, 0.3)' : 'none'
              }}
              className="w-[60px] h-[80px] rounded-lg border bg-black/80 flex flex-col items-center justify-center p-2"
            >
              <Award className={`h-6 w-6 ${isOptimizerActive ? 'text-neon-purple animate-bounce' : 'text-white/20'}`} />
              <span className="font-mono text-[9px] font-bold text-white mt-1 text-center truncate w-full">
                {activeWinner === 's_discount' ? 'Discount' :
                 activeWinner === 's_hardline' ? 'Hardline' :
                 activeWinner === 's_bundle' ? 'Bundle' : 'Personalized'}
              </span>
            </motion.div>
          </foreignObject>

        </svg>

        {/* CSS Animation injected locally for SVG stroke-dashoffset */}
        <style jsx>{`
          @keyframes flow {
            to {
              stroke-dashoffset: 0;
            }
          }
        `}</style>

      </div>
    </div>
  );
}
