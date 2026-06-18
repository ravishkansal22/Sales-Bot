'use client';

import React from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts';
import { AreaChart, TrendingUp } from 'lucide-react';

export default function TwinEvolution() {
  const { twinHistory } = useNegotiationState();

  if (!twinHistory || twinHistory.length === 0) {
    return (
      <div className="glass-panel rounded-xl p-5 flex flex-col justify-center items-center h-full min-h-[200px]">
        <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
        <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
          EVALUATING HISTORICAL DRIFT...
        </span>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[220px]">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div className="flex items-center space-x-2">
          <TrendingUp className="h-4 w-4 text-cyan-glow" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            Digital Twin Evolution Timeline
          </span>
        </div>
        <span className="rounded-full bg-white/5 border border-white/10 px-2 py-0.5 font-mono text-[8px] text-white/40 uppercase">
          Source: GET /customers/cust_1/twin-history
        </span>
      </div>

      {/* Recharts LineChart */}
      <div className="flex-1 min-h-[160px] w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={twinHistory}
            margin={{ top: 5, right: 10, left: -25, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
            <XAxis 
              dataKey="timestamp" 
              tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 8, fontFamily: 'monospace' }} 
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              tickLine={false}
            />
            <YAxis 
              domain={[0, 100]}
              tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 8, fontFamily: 'monospace' }} 
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(8, 10, 18, 0.95)',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                fontSize: '10px',
                fontFamily: 'monospace'
              }}
            />
            <Legend 
              iconSize={6}
              iconType="circle"
              wrapperStyle={{
                fontSize: '8px',
                fontFamily: 'monospace',
                paddingTop: '8px'
              }}
            />
            <Line 
              type="monotone" 
              dataKey="priceSensitivity" 
              name="Price Sensitivity" 
              stroke="#f59e0b" 
              strokeWidth={1.5}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
            <Line 
              type="monotone" 
              dataKey="urgency" 
              name="Urgency" 
              stroke="#f43f5e" 
              strokeWidth={1.5}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
            <Line 
              type="monotone" 
              dataKey="riskAversion" 
              name="Risk Aversion" 
              stroke="#10b981" 
              strokeWidth={1.5}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
            <Line 
              type="monotone" 
              dataKey="decisionSpeed" 
              name="Decision Speed" 
              stroke="#00f2fe" 
              strokeWidth={1.5}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}
