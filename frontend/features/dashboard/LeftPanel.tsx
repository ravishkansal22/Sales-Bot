'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { MessageSquare, Calendar, AlertTriangle, HelpCircle, CheckCircle, TrendingUp, Compass, Cpu } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function LeftPanel() {
  const { messages, timelineEvents, isReplaying, playbackStep } = useNegotiationState();

  const getTimelineIcon = (type: string) => {
    switch (type) {
      case 'objection': return <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />;
      case 'price': return <TrendingUp className="h-3.5 w-3.5 text-cyan-glow" />;
      case 'urgency': return <Calendar className="h-3.5 w-3.5 text-amber-500" />;
      case 'strategy': return <Compass className="h-3.5 w-3.5 text-indigo-400" />;
      case 'simulation': return <Cpu className="h-3.5 w-3.5 text-emerald-400" />;
      case 'optimizer': return <CheckCircle className="h-3.5 w-3.5 text-cyan-glow animate-pulse" />;
      default: return <HelpCircle className="h-3.5 w-3.5 text-white/50" />;
    }
  };

  return (
    <div className="flex h-full flex-col space-y-6">
      
      {/* Customer Conversation Panel */}
      <div className="glass-panel rounded-xl p-5 flex flex-col h-[45%] min-h-[300px]">
        <div className="flex items-center space-x-2 border-b border-white/10 pb-3 mb-4">
          <MessageSquare className="h-4 w-4 text-cyan-glow" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Customer Intelligence Feed
          </span>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin">
          <AnimatePresence initial={false}>
            {messages.map((msg, index) => {
              const isCustomer = msg.sender === 'customer';
              const isObjectionMessage = msg.id === 'm1' || msg.id === 'm3';
              
              // If replaying, only show messages if we are at step 1 or higher
              if (isReplaying && playbackStep < 1 && index > 0) return null;

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 15, scale: 0.98 }}
                  animate={{ 
                    opacity: 1, 
                    y: 0, 
                    scale: 1,
                    boxShadow: isReplaying && playbackStep === 1 && isObjectionMessage
                      ? '0 0 12px rgba(245, 158, 11, 0.15)'
                      : 'none'
                  }}
                  transition={{ duration: 0.45, ease: 'easeOut' }}
                  className={`flex flex-col max-w-[85%] rounded-lg p-3.5 border transition-all ${
                    isCustomer
                      ? `self-start bg-white/[0.02] border-white/15 text-white/90 mr-auto ${
                          isReplaying && playbackStep === 1 && isObjectionMessage
                            ? 'border-amber-500/40 bg-amber-500/[0.02]'
                            : ''
                        }`
                      : 'self-end bg-cyan-glow/5 border-cyan-glow/20 text-white ml-auto'
                  }`}
                >
                  <div className="flex items-center justify-between space-x-4 mb-1 border-b border-white/5 pb-1">
                    <span className="font-mono text-[9px] font-bold tracking-wider uppercase opacity-60">
                      {isCustomer ? 'LogiCore (Client)' : 'System Response'}
                    </span>
                    <span className="font-mono text-[8px] opacity-40">{msg.timestamp}</span>
                  </div>
                  <p className="text-xs leading-relaxed font-sans">{msg.text}</p>

                  {isReplaying && playbackStep === 1 && isObjectionMessage && isCustomer && (
                    <div className="mt-2 text-[9px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 flex items-center space-x-1">
                      <span className="h-1 w-1 rounded-full bg-amber-400 animate-ping"></span>
                      <span>OBJECTION EXTRACTED: COMPETITOR VALUE THREAT</span>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {/* Negotiation Timeline Panel */}
      <div className="glass-panel rounded-xl p-5 flex flex-col flex-1 min-h-[350px]">
        <div className="flex items-center space-x-2 border-b border-white/10 pb-3 mb-4">
          <TrendingUp className="h-4 w-4 text-cyan-glow" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Negotiation Simulation Timeline
          </span>
        </div>

        <div className="flex-1 overflow-y-auto pr-1">
          <div className="relative border-l border-white/10 pl-6 ml-3 space-y-6 py-2">
            <AnimatePresence>
              {timelineEvents.map((evt, idx) => {
                const isLatest = idx === timelineEvents.length - 1;
                
                return (
                  <motion.div
                    key={evt.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="relative group"
                  >
                    {/* Floating Glow Dot */}
                    <div className={`absolute -left-[31px] top-1.5 flex h-4.5 w-4.5 items-center justify-center rounded-full border bg-black transition-all ${
                      isLatest 
                        ? 'border-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.5)] scale-110' 
                        : 'border-white/20'
                    }`}>
                      {getTimelineIcon(evt.type)}
                    </div>

                    <div className={`p-3 rounded-lg border transition-all ${
                      isLatest 
                        ? 'bg-white/[0.04] border-white/15 shadow-[0_0_15px_rgba(255,255,255,0.02)]' 
                        : 'bg-transparent border-transparent'
                    }`}>
                      <div className="flex items-center justify-between">
                        <span className={`font-mono text-[10px] font-bold tracking-wide ${
                          evt.status === 'warning' ? 'text-amber-400' :
                          evt.status === 'success' ? 'text-emerald-400' : 'text-cyan-glow'
                        }`}>
                          {evt.title}
                        </span>
                        <span className="font-mono text-[8px] opacity-40">{evt.timestamp}</span>
                      </div>
                      <p className="text-xs text-white/60 mt-1 font-sans leading-relaxed">
                        {evt.description}
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
            
            {/* Playback Loader placeholder */}
            {isReplaying && timelineEvents.length < 6 && (
              <div className="relative pl-1">
                <div className="absolute -left-[27px] top-1.5 h-2 w-2 rounded-full bg-cyan-glow animate-ping" />
                <span className="font-mono text-[9px] text-white/30 tracking-widest animate-pulse">
                  SIMULATING NEXT EVENT PATHWAY...
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
      
    </div>
  );
}
