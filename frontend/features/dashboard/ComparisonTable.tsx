'use client';

import React, { useState } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { SimulationOutput } from '../../types/api';
import { ArrowUpDown, Table, Check } from 'lucide-react';

type SortKey = 'name' | 'expectedProfit' | 'expectedValue' | 'marginRetention' | 'closeProbability' | 'riskScore' | 'confidenceScore';

export default function ComparisonTable() {
  const { simulations, selectedStrategyId, setSelectedStrategyId } = useNegotiationState();
  const [sortKey, setSortKey] = useState<SortKey>('expectedValue');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const sortedData = [...simulations].sort((a, b) => {
    let valA = a[sortKey];
    let valB = b[sortKey];

    if (typeof valA === 'string' && typeof valB === 'string') {
      return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    
    if (typeof valA === 'number' && typeof valB === 'number') {
      return sortOrder === 'asc' ? valA - valB : valB - valA;
    }

    return 0;
  });

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  };

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[220px]">
      
      {/* Header */}
      <div className="flex items-center space-x-2 border-b border-white/10 pb-3 mb-4">
        <Table className="h-4 w-4 text-cyan-glow" />
        <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
          Strategy Comparison Matrix
        </span>
      </div>

      {/* Bloomberg Table Grid */}
      <div className="flex-1 overflow-x-auto">
        <table className="w-full text-left font-mono text-[10px] text-white/70 min-w-[600px]">
          <thead>
            <tr className="border-b border-white/10 text-white/40 uppercase">
              <th className="py-2.5 px-3 font-medium">
                <button onClick={() => handleSort('name')} className="flex items-center space-x-1 hover:text-white transition-colors">
                  <span>Strategy</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('expectedProfit')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Contract Value</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('expectedValue')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Expected Value</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('marginRetention')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Margin</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('closeProbability')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Close Rate</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('riskScore')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Risk</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="py-2.5 px-3 font-medium text-right">
                <button onClick={() => handleSort('confidenceScore')} className="flex items-center space-x-1 ml-auto hover:text-white transition-colors">
                  <span>Confidence</span>
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sortedData.map((row) => {
              const isSelected = selectedStrategyId === row.id;
              
              return (
                <tr 
                  key={row.id}
                  onClick={() => setSelectedStrategyId(isSelected ? null : row.id)}
                  className={`cursor-pointer transition-colors ${
                    isSelected 
                      ? 'bg-cyan-glow/10 text-white font-bold' 
                      : 'hover:bg-white/[0.02]'
                  }`}
                >
                  <td className="py-3 px-3 flex items-center space-x-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${
                      isSelected ? 'bg-cyan-glow animate-ping' : 'bg-white/20'
                    }`} />
                    <span className="truncate max-w-[150px]">{row.name}</span>
                  </td>
                  <td className="py-3 px-3 text-right text-white">
                    {formatCurrency(row.expectedProfit)}
                  </td>
                  <td className="py-3 px-3 text-right font-bold text-cyan-glow">
                    {formatCurrency(row.expectedValue)}
                  </td>
                  <td className="py-3 px-3 text-right text-white/90">
                    {(row.marginRetention * 100).toFixed(0)}%
                  </td>
                  <td className="py-3 px-3 text-right text-emerald-400">
                    {(row.closeProbability * 100).toFixed(0)}%
                  </td>
                  <td className={`py-3 px-3 text-right font-bold ${
                    row.riskScore >= 70 ? 'text-rose-400' :
                    row.riskScore >= 40 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {row.riskScore}/100
                  </td>
                  <td className="py-3 px-3 text-right text-white/60">
                    {(row.confidenceScore * 100).toFixed(0)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </div>
  );
}
