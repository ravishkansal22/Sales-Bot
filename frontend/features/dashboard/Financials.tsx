'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { DollarSign, Percent, TrendingUp, ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Financials() {
  const { simulations, selectedStrategyId, isReplaying, playbackStep, activeProduct } = useNegotiationState();

  if (!activeProduct) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="glass-panel rounded-xl p-4.5 flex flex-col justify-between space-y-4 border border-white/5 bg-white/[0.01]">
            <div className="space-y-3 animate-pulse w-full">
              <div className="h-3 bg-white/5 rounded w-2/3"></div>
              <div className="h-6 bg-white/10 rounded w-1/2"></div>
              <div className="h-3 bg-white/5 rounded w-5/6"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // If replaying and we haven't reached step 5 (financial evaluation completed), show skeleton loading
  const showSkeleton = isReplaying && playbackStep < 5;

  const currentStrategy = simulations.find(s => s.id === selectedStrategyId) || simulations[2]; // fallback to s_bundle

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  };

  const getKPIs = () => {
    if (!currentStrategy) return [];
    
    // Dynamically derive some realistic KPIs based on the currently selected strategy
    const expectedProfit = currentStrategy.expectedProfit;
    const expectedValue = currentStrategy.expectedValue;
    const margin = currentStrategy.marginRetention;
    const closeRate = currentStrategy.closeProbability;

    // Calculate dynamic variance indicators
    const isDiscount = currentStrategy.id === 's_discount';
    const isHardline = currentStrategy.id === 's_hardline';
    const isBundle = currentStrategy.id === 's_bundle';

    return [
      {
        id: 'rev',
        title: 'Projected Revenue (ACV)',
        value: formatCurrency(expectedProfit),
        delta: isDiscount ? '-30.0%' : isHardline ? '0.0%' : isBundle ? '-15.0%' : '-20.0%',
        trend: isHardline ? 'neutral' : 'down',
        desc: `Contract size relative to target (₹${activeProduct.price.toLocaleString()})`,
        sparkline: 'M 0,10 L 10,12 L 20,8 L 30,15 L 40,5 L 50,8',
        color: isHardline ? 'text-cyan-glow' : 'text-rose-400'
      },
      {
        id: 'val',
        title: 'Net Expected Value (EV)',
        value: formatCurrency(expectedValue),
        delta: isDiscount ? '+158.0%' : isHardline ? '-75.0%' : isBundle ? '+205.0%' : '+172.0%',
        trend: isHardline ? 'down' : 'up',
        desc: 'Probability × contract value',
        sparkline: isHardline ? 'M 0,2 L 10,8 L 20,12 L 30,14 L 40,16 L 50,18' : 'M 0,18 L 10,15 L 20,10 L 30,8 L 40,4 L 50,2',
        color: isHardline ? 'text-rose-500' : 'text-emerald-400'
      },
      {
        id: 'margin',
        title: 'Margin Retention Rate',
        value: `${(margin * 100).toFixed(0)}%`,
        delta: isDiscount ? '-12.0%' : isHardline ? '+25.0%' : isBundle ? '+3.5%' : '+18.0%',
        trend: isDiscount ? 'down' : 'up',
        desc: 'Retention after concessions',
        sparkline: isDiscount ? 'M 0,5 L 10,8 L 20,10 L 30,12 L 40,14 L 50,16' : 'M 0,16 L 10,14 L 20,10 L 30,8 L 40,6 L 50,4',
        color: isDiscount ? 'text-rose-400' : 'text-emerald-400'
      },
      {
        id: 'leakage',
        title: 'Contract Leakage Risk',
        value: isDiscount ? formatCurrency(activeProduct.price * 0.3) : isHardline ? formatCurrency(activeProduct.price * 0.75) : isBundle ? formatCurrency(activeProduct.price * 0.15) : formatCurrency(activeProduct.price * 0.2),
        delta: isDiscount ? '+50.0%' : isHardline ? '+275.0%' : isBundle ? '-10.0%' : '0.0%',
        trend: isHardline ? 'up' : isBundle ? 'down' : 'neutral',
        desc: 'Projected value lost to concessions/churn',
        sparkline: isHardline ? 'M 0,18 L 10,14 L 20,10 L 30,8 L 40,4 L 50,2' : 'M 0,2 L 10,6 L 20,8 L 30,12 L 40,15 L 50,18',
        color: isHardline ? 'text-rose-500' : isBundle ? 'text-emerald-400' : 'text-white/40'
      }
    ];
  };

  const kpis = getKPIs();

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {kpis.map((kpi, idx) => {
        const isUp = kpi.trend === 'up';
        const isDown = kpi.trend === 'down';

        return (
          <div key={kpi.id} className="glass-panel rounded-xl p-4.5 flex flex-col justify-between space-y-4 border border-white/5 bg-white/[0.01]">
            {showSkeleton ? (
              <div className="space-y-3 animate-pulse w-full">
                <div className="h-3 bg-white/5 rounded w-2/3"></div>
                <div className="h-6 bg-white/10 rounded w-1/2"></div>
                <div className="h-3 bg-white/5 rounded w-5/6"></div>
              </div>
            ) : (
              <>
                {/* KPI Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-[9px] text-white/40 leading-none block uppercase">
                      {kpi.title}
                    </span>
                    <span className="font-mono text-[16px] font-bold text-white tracking-wide mt-1.5 block">
                      {kpi.value}
                    </span>
                  </div>
                  
                  {/* Delta Badges */}
                  <span className={`flex items-center space-x-0.5 rounded px-1.5 py-0.5 font-mono text-[8px] font-bold ${
                    isUp ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                    isDown ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                    'bg-white/5 text-white/50 border border-white/10'
                  }`}>
                    {isUp && <ArrowUpRight className="h-2.5 w-2.5" />}
                    {isDown && <ArrowDownRight className="h-2.5 w-2.5" />}
                    <span>{kpi.delta}</span>
                  </span>
                </div>

                {/* Trend line and desc */}
                <div className="flex items-center justify-between pt-2 border-t border-white/5">
                  <span className="font-sans text-[9px] text-white/50 leading-relaxed max-w-[65%]">
                    {kpi.desc}
                  </span>
                  
                  {/* Small Sparkline SVG */}
                  <svg className={`w-12 h-6 ${kpi.color}`} viewBox="0 0 50 20">
                    <path 
                      d={kpi.sparkline} 
                      fill="none" 
                      stroke="currentColor" 
                      strokeWidth="1.5" 
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
