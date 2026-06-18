'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { FileText, Percent, Info, Award, HelpCircle, CheckCircle, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';

export default function DealSummaryPanel() {
  const { dealSummary, activeProduct } = useNegotiationState();
  const pathname = usePathname();

  if (!dealSummary) {
    return (
      <div className="glass-panel rounded-xl p-5 flex flex-col justify-center items-center h-full min-h-[300px]">
        <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
        <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
          Compiling Deal Summary...
        </span>
      </div>
    );
  }

  // Radial Progress Ring values for Confidence Score
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const confidencePct = Math.round(dealSummary.confidenceScore * 100);
  const strokeDashoffset = circumference - (confidencePct / 100) * circumference;

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  };

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes('ratified') || s.includes('concluded') || s.includes('final')) return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5';
    if (s.includes('threat') || s.includes('objection')) return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
    return 'text-cyan-glow border-cyan-glow/20 bg-cyan-glow/5';
  };

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[400px]">
      
      {/* Title */}
      <div className="flex items-center space-x-2 border-b border-white/10 pb-3 mb-4">
        <FileText className="h-4 w-4 text-cyan-glow" />
        <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
          Current Deal Summary
        </span>
      </div>

      <div className="space-y-5 flex-1 flex flex-col justify-between">
        
        <div className="space-y-4">
          
          {/* Active Product Name */}
          <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg">
            <span className="font-mono text-[9px] text-white/30 uppercase block tracking-wider">
              Selected Agreement Item
            </span>
            <span className="font-sans text-xs font-bold text-white mt-1 block uppercase">
              {activeProduct.name}
            </span>
            <div className="flex justify-between mt-2 font-mono text-[10px] border-t border-white/5 pt-2">
              <span className="text-white/40">CATALOG VALUE:</span>
              <span className="text-white/80">₹{activeProduct.price.toLocaleString()}</span>
            </div>
          </div>

          {/* Pricing Concessions */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
              <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                Request Discount
              </span>
              <span className="font-mono text-sm font-bold text-amber-400 block mt-1.5 leading-none">
                {dealSummary.customerDiscountRequest}%
              </span>
            </div>
            
            <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
              <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                Calibrated Offer
              </span>
              <span className="font-mono text-sm font-bold text-cyan-glow block mt-1.5 leading-none">
                ₹{dealSummary.currentAiOfferPrice.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Bundle items list */}
          {dealSummary.bundleItems.length > 0 ? (
            <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg space-y-1.5">
              <span className="font-mono text-[9px] text-white/30 uppercase block tracking-wider border-b border-white/5 pb-1">
                Concession Package
              </span>
              {dealSummary.bundleItems.map((item, idx) => (
                <div key={idx} className="flex items-center space-x-1.5 text-[10px] text-emerald-400 font-sans">
                  <CheckCircle className="h-3 w-3 shrink-0" />
                  <span className="truncate">{item}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg text-center">
              <span className="font-mono text-[9px] text-white/30 uppercase tracking-widest leading-none block py-1">
                No Bundles Added
              </span>
            </div>
          )}

          {/* Close Probability */}
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[9px] text-white/40 leading-none">
              <span>ESTIMATED CLOSE PROBABILITY</span>
              <span className="font-bold text-white">{(dealSummary.closeProbability * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${dealSummary.closeProbability * 100}%` }}
                className="h-full bg-cyan-glow shadow-[0_0_8px_rgba(0,242,254,0.4)]"
              />
            </div>
          </div>

          {/* Status badge */}
          <div className="flex items-center justify-between border-t border-white/5 pt-3">
            <span className="font-mono text-[9px] text-white/40 uppercase leading-none">
              Deal Status
            </span>
            <span className={`rounded-md border px-2 py-0.5 font-mono text-[9px] font-bold uppercase ${getStatusColor(dealSummary.status)}`}>
              {dealSummary.status}
            </span>
          </div>

        </div>

        {/* Confidence Indicator Circle */}
        <div className="border-t border-white/10 pt-4 flex items-center justify-between bg-white/[0.005] -mx-5 -mb-5 p-5 rounded-b-xl">
          <div className="flex flex-col text-left">
            <span className="font-mono text-[9px] text-white/30 uppercase leading-none block">
              Simulation Telemetry
            </span>
            <span className="font-mono text-[10px] font-bold text-white mt-1 block uppercase tracking-wider">
              Negotiation Confidence
            </span>
            <span className="font-mono text-[8px] text-white/40 leading-none mt-1">
              Objective: {dealSummary.optimizationObjective}
            </span>
          </div>

          <div className="relative flex h-14 w-14 items-center justify-center shrink-0">
            {/* SVG circle */}
            <svg className="absolute inset-0 w-full h-full -rotate-90">
              <circle
                cx="28"
                cy="28"
                r={radius}
                className="text-white/5"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
              />
              <motion.circle
                cx="28"
                cy="28"
                r={radius}
                className="text-cyan-glow"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset }}
                transition={{ duration: 0.8 }}
                style={{
                  filter: 'drop-shadow(0px 0px 4px rgba(0, 242, 254, 0.4))'
                }}
              />
            </svg>
            <span className="font-mono text-[11px] font-bold text-white z-10">
              {confidencePct}%
            </span>
          </div>
        </div>

      </div>

    </div>
  );
}
