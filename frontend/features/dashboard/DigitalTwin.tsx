'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { User, Award, ShieldAlert, Zap, Heart, Flame } from 'lucide-react';
import { motion } from 'framer-motion';

export default function DigitalTwin() {
  const { twinProfile, isReplaying, playbackStep } = useNegotiationState();

  if (!twinProfile) {
    return (
      <div className="glass-panel rounded-xl p-5 flex flex-col justify-center items-center h-full min-h-[300px]">
        <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
        <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
          CALCULATING CUSTOMER PROFILE...
        </span>
      </div>
    );
  }

  // Radar chart data mapping
  const chartData = [
    { subject: 'Price Sensitivity', value: twinProfile.priceSensitivity },
    { subject: 'Urgency', value: twinProfile.urgency },
    { subject: 'Risk Aversion', value: twinProfile.riskAversion },
    { subject: 'Brand Loyalty', value: twinProfile.brandLoyalty },
    { subject: 'Decision Speed', value: twinProfile.decisionSpeed }
  ];

  // Radial progress ring helper
  const RadialRing = ({ value, label, colorClass, icon }: { value: number; label: string; colorClass: string; icon: React.ReactNode }) => {
    const radius = 18;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (value / 100) * circumference;

    return (
      <div className="flex flex-col items-center justify-center p-3 rounded-lg border border-white/5 bg-black/30 w-full">
        <div className="relative flex items-center justify-center h-16 w-16 mb-2">
          {/* Progress Ring */}
          <svg className="absolute inset-0 w-full h-full -rotate-90">
            <circle
              cx="32"
              cy="32"
              r={radius}
              className="text-white/5"
              strokeWidth="3.5"
              stroke="currentColor"
              fill="none"
            />
            <motion.circle
              cx="32"
              cy="32"
              r={radius}
              className={colorClass}
              strokeWidth="3.5"
              stroke="currentColor"
              fill="none"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset }}
              transition={{ duration: 1, ease: 'easeOut' }}
            />
          </svg>
          <div className="z-10 flex items-center justify-center text-white/70">
            {icon}
          </div>
        </div>
        <span className="font-mono text-[9px] text-white/50 tracking-wider text-center leading-none mb-1 uppercase">
          {label}
        </span>
        <span className="font-mono text-[13px] font-bold text-white leading-none">
          {value}%
        </span>
      </div>
    );
  };

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[300px]">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div className="flex items-center space-x-2">
          <User className="h-4 w-4 text-cyan-glow" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Customer Digital Twin
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="font-mono text-[9px] text-white/40 uppercase">Profile Score:</span>
          <span className="rounded bg-cyan-glow/10 border border-cyan-glow/30 px-2 py-0.5 font-mono text-[10px] font-bold text-cyan-glow">
            {twinProfile.overallProfileScore}/100
          </span>
        </div>
      </div>

      {/* Main split: radar vs telemetry list */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
        
        {/* Left: Persona Details & Radar */}
        <div className="flex flex-col justify-between space-y-4">
          <div className="rounded-lg border border-white/5 bg-white/[0.01] p-3.5">
            <span className="font-mono text-[9px] text-cyan-glow tracking-wider uppercase font-bold">
              Detected Persona Model
            </span>
            <p className="font-sans text-xs font-bold text-white mt-1">
              {twinProfile.personaName}
            </p>
            <p className="font-sans text-[11px] text-white/50 mt-1.5 leading-relaxed">
              {twinProfile.description}
            </p>
          </div>

          {/* Recharts Radar Chart */}
          <div className="h-[150px] w-full flex items-center justify-center relative bg-black/10 rounded-lg border border-white/5 p-1">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={chartData}>
                <PolarGrid stroke="rgba(255,255,255,0.06)" />
                <PolarAngleAxis 
                  dataKey="subject" 
                  tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 7, fontFamily: 'monospace' }} 
                />
                <PolarRadiusAxis 
                  angle={30} 
                  domain={[0, 100]} 
                  tick={false}
                  axisLine={false}
                />
                <Radar 
                  name="Digital Twin" 
                  dataKey="value" 
                  stroke="#00f2fe" 
                  fill="#00f2fe" 
                  fillOpacity={0.15} 
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Radial progress matrix */}
        <div className="grid grid-cols-2 gap-2.5">
          <RadialRing 
            value={twinProfile.priceSensitivity} 
            label="Price Sensitivity" 
            colorClass="text-amber-500" 
            icon={<ShieldAlert className="h-4 w-4" />} 
          />
          <RadialRing 
            value={twinProfile.urgency} 
            label="Urgency Level" 
            colorClass="text-rose-500" 
            icon={<Flame className="h-4 w-4 animate-pulse" />} 
          />
          <RadialRing 
            value={twinProfile.riskAversion} 
            label="Risk Aversion" 
            colorClass="text-emerald-400" 
            icon={<Award className="h-4 w-4" />} 
          />
          <RadialRing 
            value={twinProfile.decisionSpeed} 
            label="Decision Speed" 
            colorClass="text-cyan-glow" 
            icon={<Zap className="h-4 w-4" />} 
          />
        </div>

      </div>

    </div>
  );
}
