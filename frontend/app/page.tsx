'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  ArrowRight, ShieldCheck, Cpu, Database, 
  Award, BarChart3, TrendingUp, Sparkles, Zap, Network, Code, MessageSquare
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GridBackground from '../components/GridBackground';

export default function LandingPage() {
  const [activeThinkStep, setActiveThinkStep] = useState(0);

  // Auto-advance the "How Ghost Negotiator Thinks" visualization steps
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveThinkStep((prev) => (prev + 1) % 6);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const thinkSteps = [
    {
      title: "1. Customer Message",
      desc: "Contract dispute or objection is parsed for budget & competitor leverage details.",
      icon: <MessageSquare className="h-5 w-5 text-amber-400" />,
      color: "border-amber-500/30 text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.15)]"
    },
    {
      title: "2. Digital Twin Calibration",
      desc: "The buyer behavioral profile recalculates price sensitivity, urgency, and loyalty metrics.",
      icon: <Database className="h-5 w-5 text-cyan-glow" />,
      color: "border-cyan-glow/30 text-cyan-glow shadow-[0_0_15px_rgba(0,242,254,0.15)]"
    },
    {
      title: "3. Strategy Generation",
      desc: "Four custom options (Discount, Hardline, Bundle, Personalized) are created.",
      icon: <Network className="h-5 w-5 text-indigo-400" />,
      color: "border-indigo-500/30 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.15)]"
    },
    {
      title: "4. Future Simulations",
      desc: "Evaluates 24 simulated negotiation rollouts, predicting actions & reactions.",
      icon: <Cpu className="h-5 w-5 text-emerald-400" />,
      color: "border-emerald-500/30 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.15)]"
    },
    {
      title: "5. Financial Analysis",
      desc: "Audits expected lifetime value, profit retention, and contract leakage margins.",
      icon: <BarChart3 className="h-5 w-5 text-cyan-glow" />,
      color: "border-cyan-glow/30 text-cyan-glow shadow-[0_0_15px_rgba(0,242,254,0.15)]"
    },
    {
      title: "6. Optimizer Recommendation",
      desc: "Selected strategy recommendation is dispatched with confidence score metrics.",
      icon: <Award className="h-5 w-5 text-neon-purple" />,
      color: "border-neon-purple/30 text-neon-purple shadow-[0_0_15px_rgba(139,92,246,0.15)]"
    }
  ];

  return (
    <div className="relative min-h-screen bg-deep-black text-slate-100 flex flex-col z-0">
      
      {/* Animated network particles background */}
      <GridBackground />

      {/* Header */}
      <header className="w-full border-b border-white/10 bg-black/60 backdrop-blur-md px-6 py-4 sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-glow/30 bg-cyan-glow/5">
              <Zap className="h-4 w-4 text-cyan-glow animate-pulse" />
            </div>
            <span className="font-mono text-base font-bold tracking-wider text-white">
              GHOST <span className="text-cyan-glow">NEGOTIATOR</span>
            </span>
          </div>

          <div className="flex items-center space-x-6">
            <Link 
              href="/dashboard"
              className="relative rounded-lg border border-cyan-glow/30 bg-cyan-glow/10 px-4 py-2 font-mono text-xs text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.1)] hover:shadow-[0_0_15px_rgba(0,242,254,0.3)] hover:bg-cyan-glow/20 transition-all flex items-center space-x-1"
            >
              <span>ENTER INTEL ROOM</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative px-6 py-20 lg:py-32 flex flex-col items-center justify-center text-center max-w-5xl mx-auto overflow-hidden">
        
        {/* Floating gradient orb background */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-cyan-glow/10 blur-[120px] rounded-full -z-10 pointer-events-none"></div>
        <div className="absolute top-1/3 left-1/3 w-[300px] h-[300px] bg-neon-purple/10 blur-[100px] rounded-full -z-10 pointer-events-none"></div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="space-y-6"
        >
          <span className="inline-flex items-center space-x-1.5 rounded-full border border-cyan-glow/30 bg-cyan-glow/5 px-4 py-1.5 font-mono text-[10px] tracking-widest text-cyan-glow uppercase">
            <Sparkles className="h-3.5 w-3.5 animate-spin" />
            <span>Next-Gen Revenue Intelligence Operating System</span>
          </span>

          <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold tracking-tight text-white leading-tight font-sans">
            AI That Simulates <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-cyan-glow via-blue-500 to-neon-purple bg-clip-text text-transparent">
              Negotiation Futures
            </span> <br />
            Before Making Decisions
          </h1>

          <p className="text-base sm:text-lg text-slate-400 max-w-3xl mx-auto font-sans leading-relaxed">
            Ghost Negotiator evaluates multiple B2B negotiation strategies, predicts customer reactions, 
            calculates financial outcomes, and selects the optimal business strategy to maximize yield and eliminate churn.
          </p>

          <div className="pt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/workspace"
              className="relative px-8 py-3.5 rounded-lg bg-cyan-glow text-black font-mono text-sm font-bold shadow-[0_0_20px_rgba(0,242,254,0.3)] hover:shadow-[0_0_30px_rgba(0,242,254,0.5)] hover:bg-cyan-glow-light transition-all flex items-center space-x-2"
            >
              <span>Start Negotiation</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="px-8 py-3.5 rounded-lg border border-white/10 bg-white/5 font-mono text-sm text-white hover:bg-white/10 hover:border-white/20 transition-all flex items-center space-x-2"
            >
              <span>Explore AI Command Center</span>
            </Link>
          </div>
        </motion.div>

        {/* Dashboard Mockup Preview */}
        <motion.div
          initial={{ opacity: 0, y: 65 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.3 }}
          className="mt-20 w-full max-w-5xl rounded-2xl border border-white/10 bg-black/60 p-2 shadow-[0_0_50px_rgba(0,0,0,0.8)] backdrop-blur-md relative group"
        >
          {/* Cyber scanline indicator */}
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-cyan-glow via-blue-500 to-neon-purple shadow-[0_0_10px_rgba(0,242,254,0.5)]"></div>
          
          <div className="rounded-xl overflow-hidden border border-white/5 bg-black/90 aspect-[16/9] relative flex items-center justify-center">
            
            {/* Simulation Interface Mockup Graphic */}
            <div className="absolute inset-0 p-6 flex flex-col justify-between font-mono text-[9px] text-white/40">
              <div className="flex justify-between border-b border-white/10 pb-4">
                <span>SYSTEM: SIMULATION ENGINE ONLINE</span>
                <span className="text-cyan-glow">DEMO PREVIEW</span>
              </div>
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-4">
                  <div className="relative inline-flex h-20 w-20 items-center justify-center rounded-full border border-cyan-glow/30 bg-cyan-glow/5">
                    <div className="absolute inset-0 rounded-full border border-cyan-glow animate-ping opacity-25"></div>
                    <Cpu className="h-8 w-8 text-cyan-glow animate-pulse" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-widest uppercase">GHOST PLATFORM SIMULATOR</h3>
                    <p className="text-[10px] text-white/50 max-w-sm mt-1 mx-auto leading-relaxed">
                      Click launch to enter the live dashboard, trigger playbacks, alter optimization models, and explore rollouts.
                    </p>
                  </div>
                  <Link 
                    href="/workspace"
                    className="inline-block rounded border border-cyan-glow/30 bg-cyan-glow/5 px-4 py-1.5 text-cyan-glow font-bold uppercase hover:bg-cyan-glow/20 transition-all"
                  >
                    Enter Live Workspace
                  </Link>
                </div>
              </div>
              <div className="flex justify-between border-t border-white/10 pt-4">
                <span>REPORTS: 24 SCENARIOS EVALUATED</span>
                <span>YIELD RETENTION: 82%</span>
              </div>
            </div>
            
          </div>
        </motion.div>

      </section>

      {/* "How Ghost Negotiator Thinks" - Animated pipeline section */}
      <section className="px-6 py-20 bg-black/30 border-t border-white/5">
        <div className="max-w-6xl mx-auto space-y-16">
          <div className="text-center space-y-4">
            <span className="font-mono text-xs font-bold text-cyan-glow tracking-widest uppercase">
              Engine Pipeline Workflow
            </span>
            <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-white">
              How Ghost Negotiator Thinks
            </h2>
            <p className="text-sm text-slate-400 max-w-2xl mx-auto font-sans leading-relaxed">
              Our simulation engine routes incoming customer conversations through our digital twin and financial models continuously in a multi-step loop.
            </p>
          </div>

          {/* Sequential Step Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {thinkSteps.map((step, idx) => {
              const isActive = activeThinkStep === idx;
              
              return (
                <div
                  key={idx}
                  className={`glass-panel rounded-xl p-5 border transition-all duration-500 ${
                    isActive 
                      ? step.color 
                      : 'border-white/5 bg-white/[0.005] opacity-50 scale-98'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="p-2 bg-white/5 rounded-lg border border-white/10">
                      {step.icon}
                    </div>
                    {isActive && (
                      <span className="font-mono text-[9px] text-cyan-glow font-bold uppercase tracking-widest animate-pulse">
                        Active Node
                      </span>
                    )}
                  </div>
                  <h3 className="font-mono text-xs font-bold text-white uppercase">{step.title}</h3>
                  <p className="text-[11px] text-white/50 mt-2 font-sans leading-relaxed">
                    {step.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Product Overview Feature matrix Grid */}
      <section className="px-6 py-20 max-w-6xl mx-auto space-y-16">
        <div className="text-center space-y-4">
          <span className="font-mono text-xs font-bold text-cyan-glow tracking-widest uppercase">
            Platform Capabilities
          </span>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-white">
            Revenue Intelligence Architecture
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Feature 1: Future Simulation Engine */}
          <div className="glass-panel rounded-xl p-5 space-y-4">
            <Cpu className="h-6 w-6 text-cyan-glow" />
            <h3 className="font-mono text-xs font-bold text-white uppercase">Future Simulation Engine</h3>
            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              Branch pricing actions into 24 distinct parallel futures. Predict concessions, objection responses, and competitive fallout before signing contracts.
            </p>
          </div>

          {/* Feature 2: Customer Digital Twin */}
          <div className="glass-panel rounded-xl p-5 space-y-4">
            <Database className="h-6 w-6 text-neon-purple" />
            <h3 className="font-mono text-xs font-bold text-white uppercase">Customer Digital Twin</h3>
            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              Construct real-time profiles modeling customer price sensitivity, contract urgency, risk profiles, and brand migration thresholds.
            </p>
          </div>

          {/* Feature 3: Financial Optimization */}
          <div className="glass-panel rounded-xl p-5 space-y-4">
            <BarChart3 className="h-6 w-6 text-emerald-400" />
            <h3 className="font-mono text-xs font-bold text-white uppercase">Financial Optimization</h3>
            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              Quantify absolute ACV, net expected contract values, margin concessions, and revenue leakage indicators across all scenarios.
            </p>
          </div>

          {/* Feature 4: Strategic Optimizer */}
          <div className="glass-panel rounded-xl p-5 space-y-4">
            <Award className="h-6 w-6 text-cyan-glow" />
            <h3 className="font-mono text-xs font-bold text-white uppercase">Strategic Optimizer</h3>
            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              Enforce guardrails (Max Margin, Balanced, Close Rate) and let the AI generate recommended B2B concessions with confidence ratings.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full border-t border-white/10 bg-black/60 backdrop-blur-md px-6 py-10 mt-auto text-center font-mono text-[9px] text-white/30">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span>© 2026 GHOST NEGOTIATOR INC. ALL RIGHTS RESERVED.</span>
          <div className="flex space-x-4">
            <span className="hover:text-white transition-colors cursor-pointer">TERMS OF SERVICE</span>
            <span className="hover:text-white transition-colors cursor-pointer">PRIVACY POLICY</span>
            <span className="hover:text-white transition-colors cursor-pointer">SYSTEM STATS</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
