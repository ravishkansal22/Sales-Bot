'use client';

/**
 * ExplainabilityPanel - Read-only visualization of existing Ghost Negotiator internals.
 *
 * DATA POLICY:
 *   - READ-ONLY. Never writes to state, never triggers API calls,
 *     never influences negotiation logic, optimizer selection,
 *     discount calculations, or any business behaviour.
 *   - All values sourced from existing useNegotiationState state:
 *     twinProfile, twinHistory, optimizerResult, simulations.
 *   - Missing values display as 'Not Available'.
 *   - Trend indicators ONLY shown when twinHistory.length >= 2.
 *     When no historical comparison exists, an em-dash is shown.
 *   - No hardcoded thresholds, strategy names, product names, or customer types.
 */

import React, { useState } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Activity,
  Zap,
  AlertCircle,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Helpers - all guard against null/undefined, return 'Not Available'
// ---------------------------------------------------------------------------

function fmtPct(val: number | null | undefined): string {
  if (val == null || isNaN(val as number)) return 'Not Available';
  return `${Math.round(val as number)}%`;
}

function fmtFraction(val: number | null | undefined): string {
  if (val == null || isNaN(val as number)) return 'Not Available';
  return `${Math.round((val as number) * 100)}%`;
}

function fmtCurrency(val: number | null | undefined): string {
  if (val == null || isNaN(val as number) || val === 0) return 'Not Available';
  return `₹${Math.round(val as number).toLocaleString('en-IN')}`;
}

function fmtStr(val: string | null | undefined): string {
  if (!val || val.trim() === '') return 'Not Available';
  return val;
}

/**
 * Derive a trend direction by comparing two numeric values.
 * Only call when twinHistory.length >= 2 (genuine historical comparison).
 * Threshold of 2 points prevents noise on minor float changes.
 */
function deriveTrend(prev: number, curr: number): 'UP' | 'DOWN' | 'FLAT' {
  const delta = curr - prev;
  if (delta > 2) return 'UP';
  if (delta < -2) return 'DOWN';
  return 'FLAT';
}

// ---------------------------------------------------------------------------
// CollapsibleSection
// ---------------------------------------------------------------------------

interface CollapsibleSectionProps {
  title: string;
  icon: React.ReactNode;
  accentClass: string;
  bgClass: string;
  borderClass: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({
  title,
  icon,
  accentClass,
  bgClass,
  borderClass,
  children,
  defaultOpen = true,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`border ${borderClass} rounded-lg overflow-hidden`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center justify-between px-3 py-2.5 ${bgClass} hover:opacity-80 transition-all`}
        aria-expanded={open}
      >
        <div className="flex items-center space-x-2">
          <span className={accentClass}>{icon}</span>
          <span className={`font-mono text-[9.5px] font-bold uppercase tracking-wider ${accentClass}`}>
            {title}
          </span>
        </div>
        {open ? (
          <ChevronUp className="h-3 w-3 text-white/30" />
        ) : (
          <ChevronDown className="h-3 w-3 text-white/30" />
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-3 py-3 space-y-2.5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricRow - single labelled bar with optional trend indicator
// ---------------------------------------------------------------------------

interface MetricRowProps {
  label: string;
  value: string;
  barValue?: number;
  trendType?: 'UP' | 'DOWN' | 'FLAT';
  trendLabel?: string;
}

function MetricRow({ label, value, barValue, trendType, trendLabel }: MetricRowProps) {
  // Arrow characters encoded as unicode escapes to avoid encoding issues
  const trendChar =
    trendType === 'UP' ? '↑' : trendType === 'DOWN' ? '↓' : '→';
  const trendColorClass =
    trendType === 'UP'
      ? 'text-amber-400'
      : trendType === 'DOWN'
      ? 'text-emerald-400'
      : 'text-white/40';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] text-white/40 uppercase tracking-wider">
          {label}
        </span>
        <div className="flex items-center space-x-1.5">
          <span className="font-mono text-[10px] font-bold text-white">{value}</span>
          {trendType ? (
            <span className={`font-mono text-[10px] font-bold ${trendColorClass}`}>
              {trendChar}
            </span>
          ) : trendLabel ? (
            <span className="font-mono text-[8px] text-white/25 italic">{trendLabel}</span>
          ) : null}
        </div>
      </div>
      {barValue != null && (
        <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(Math.max(barValue, 0), 100)}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="h-full rounded-full"
            style={{
              background: 'rgba(0,242,254,0.55)',
              filter: 'drop-shadow(0 0 3px rgba(0,242,254,0.35))',
            }}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Digital Twin Sub-panel
// ---------------------------------------------------------------------------

function DigitalTwinSubPanel() {
  const { twinProfile, twinHistory } = useNegotiationState();

  if (!twinProfile) {
    return (
      <div className="flex items-center space-x-2 py-2">
        <AlertCircle className="h-3.5 w-3.5 text-white/20 shrink-0" />
        <span className="font-mono text-[9px] text-white/30 italic">
          Digital Twin profile not yet available.
        </span>
      </div>
    );
  }

  // Derive trends only when >= 2 genuine historical snapshots exist
  const hasHistory = Array.isArray(twinHistory) && twinHistory.length >= 2;
  const prevSnap = hasHistory ? twinHistory[twinHistory.length - 2] : null;

  const dimensions: Array<{
    key: keyof typeof twinProfile;
    prevKey: string;
    label: string;
  }> = [
    { key: 'priceSensitivity', prevKey: 'priceSensitivity', label: 'Price Sensitivity' },
    { key: 'urgency',          prevKey: 'urgency',           label: 'Urgency' },
    { key: 'riskAversion',     prevKey: 'riskAversion',      label: 'Risk Aversion' },
    { key: 'brandLoyalty',     prevKey: 'brandLoyalty',      label: 'Brand Loyalty' },
    { key: 'decisionSpeed',    prevKey: 'decisionSpeed',     label: 'Decision Speed' },
  ];

  return (
    <div className="space-y-2.5">
      {/* Persona badge - only rendered when personaName exists */}
      {twinProfile.personaName && (
        <div className="px-2.5 py-2 bg-cyan-glow/5 border border-cyan-glow/15 rounded-md">
          <span className="font-mono text-[8px] text-cyan-glow/50 uppercase tracking-widest block">
            Inferred Persona
          </span>
          <span className="font-sans text-[10.5px] font-bold text-cyan-glow mt-0.5 block">
            {twinProfile.personaName}
          </span>
        </div>
      )}

      {/* Dimension bars */}
      {dimensions.map(({ key, prevKey, label }) => {
        const curr = twinProfile[key] as number | undefined;
        const display = fmtPct(curr);
        const bar = curr ?? 0;

        let trendType: 'UP' | 'DOWN' | 'FLAT' | undefined;
        let trendLabel: string | undefined;

        if (hasHistory && prevSnap) {
          // Two-step cast to unknown then to Record avoids TypeScript index signature error
          const prevVal = (prevSnap as unknown as Record<string, unknown>)[prevKey] as number | undefined;
          if (prevVal != null && curr != null) {
            trendType = deriveTrend(prevVal, curr);
          }
        } else {
          // No historical comparison available - show em-dash instead of trend
          trendLabel = '—';
        }

        return (
          <MetricRow
            key={String(key)}
            label={label}
            value={display}
            barValue={bar}
            trendType={trendType}
            trendLabel={trendLabel}
          />
        );
      })}

      {/* History footnote */}
      <div className="pt-1 border-t border-white/5">
        <span className="font-mono text-[7.5px] text-white/20 italic">
          {hasHistory
            ? `${twinHistory.length} snapshots — arrows reflect shift from previous turn`
            : 'Trend comparison available from second negotiation turn onward'}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Negotiation Intelligence Sub-panel
// ---------------------------------------------------------------------------

function NegotiationIntelligenceSubPanel() {
  const { optimizerResult, simulations } = useNegotiationState();

  if (!optimizerResult) {
    return (
      <div className="flex items-center space-x-2 py-2">
        <AlertCircle className="h-3.5 w-3.5 text-white/20 shrink-0" />
        <span className="font-mono text-[9px] text-white/30 italic">
          Optimizer output not yet available.
        </span>
      </div>
    );
  }

  const isInitialState =
    optimizerResult.winningStrategyId === 's_initial' ||
    optimizerResult.winningStrategyId === 's_none' ||
    optimizerResult.winningStrategyId === 'none' ||
    optimizerResult.winningStrategyId === 'initial';

  // Derive human-readable strategy name from matching simulation entry
  const winningSim = simulations.find(
    (s) =>
      `s_${s.name}` === optimizerResult.winningStrategyId ||
      s.id === optimizerResult.winningStrategyId
  );
  const strategyLabel = isInitialState
    ? 'No Active Offer'
    : fmtStr(winningSim?.name ?? optimizerResult.winningStrategyId);

  const closeProbDisplay = winningSim
    ? fmtFraction(winningSim.closeProbability)
    : 'Not Available';
  const revenueDisplay = winningSim
    ? fmtCurrency(winningSim.expectedValue)
    : 'Not Available';
  const discountDisplay =
    optimizerResult.currentDiscountPercent != null && optimizerResult.currentDiscountPercent > 0
      ? `${Math.round(optimizerResult.currentDiscountPercent)}%`
      : isInitialState
      ? '0%'
      : 'Not Available';

  const confidencePct = Math.round((optimizerResult.confidenceScore ?? 0) * 100);
  const radius = 18;
  const circ = 2 * Math.PI * radius;
  const dashOffset = circ - (confidencePct / 100) * circ;

  return (
    <div className="space-y-3">

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="p-2 bg-white/[0.02] border border-white/5 rounded-md col-span-2">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Selected Strategy
          </span>
          <span className="font-sans text-[11px] font-bold text-white mt-0.5 block leading-tight">
            {strategyLabel}
          </span>
        </div>

        <div className="p-2 bg-white/[0.02] border border-white/5 rounded-md">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Strategies Evaluated
          </span>
          <span className="font-mono text-sm font-bold text-cyan-glow mt-0.5 block leading-none">
            {simulations.length > 0 ? String(simulations.length) : 'Not Available'}
          </span>
        </div>

        <div className="p-2 bg-white/[0.02] border border-white/5 rounded-md">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Discount Offered
          </span>
          <span className="font-mono text-sm font-bold text-amber-400 mt-0.5 block leading-none">
            {discountDisplay}
          </span>
        </div>

        <div className="p-2 bg-white/[0.02] border border-white/5 rounded-md">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Close Probability
          </span>
          <span className="font-mono text-sm font-bold text-emerald-400 mt-0.5 block leading-none">
            {closeProbDisplay}
          </span>
        </div>

        <div className="p-2 bg-white/[0.02] border border-white/5 rounded-md">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Revenue Impact
          </span>
          <span className="font-mono text-[11px] font-bold text-white mt-0.5 block leading-none">
            {revenueDisplay}
          </span>
        </div>
      </div>

      {/* Confidence ring */}
      <div className="flex items-center justify-between border border-white/5 rounded-md px-3 py-2 bg-white/[0.01]">
        <div>
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Optimizer Confidence
          </span>
          <span className="font-mono text-[9.5px] text-white/45 mt-0.5 block">
            Composite score across simulations
          </span>
        </div>
        <div className="flex flex-col items-center shrink-0 ml-3">
          <div className="relative flex h-11 w-11 items-center justify-center">
            <svg
              className="absolute inset-0 w-full h-full -rotate-90"
              viewBox="0 0 40 40"
            >
              <circle
                cx="20" cy="20" r={radius}
                stroke="rgba(255,255,255,0.05)"
                strokeWidth="3" fill="none"
              />
              <motion.circle
                cx="20" cy="20" r={radius}
                stroke="rgba(139,92,246,0.8)"
                strokeWidth="3" fill="none"
                strokeDasharray={circ}
                initial={{ strokeDashoffset: circ }}
                animate={{ strokeDashoffset: dashOffset }}
                transition={{ duration: 0.75 }}
                style={{ filter: 'drop-shadow(0 0 3px rgba(139,92,246,0.5))' }}
              />
            </svg>
            <span className="font-mono text-[9px] font-bold text-white z-10">
              {confidencePct}%
            </span>
          </div>
        </div>
      </div>

      {/* Simulated strategies list */}
      {simulations.length > 0 && (
        <div className="border border-white/5 rounded-md p-2.5 space-y-1.5">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Strategies Simulated
          </span>
          <div className="space-y-1">
            {simulations.map((sim) => {
              const isWinner =
                `s_${sim.name}` === optimizerResult.winningStrategyId ||
                sim.id === optimizerResult.winningStrategyId;
              return (
                <div
                  key={sim.id}
                  className={[
                    'flex items-center justify-between px-2 py-1 rounded text-[9px] font-mono',
                    isWinner
                      ? 'bg-cyan-glow/10 border border-cyan-glow/25 text-cyan-glow'
                      : 'bg-white/[0.01] border border-white/5 text-white/45',
                  ].join(' ')}
                >
                  <span className="truncate max-w-[120px]">{sim.name}</span>
                  <div className="flex items-center space-x-1 shrink-0 ml-1">
                    <span
                      className={`font-bold ${isWinner ? 'text-cyan-glow' : 'text-white/30'}`}
                    >
                      {fmtFraction(sim.closeProbability)}
                    </span>
                    {isWinner && (
                      <span className="text-[7px] text-cyan-glow uppercase tracking-wider">
                        {'✓'} Selected
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Winning factors */}
      {optimizerResult.winningFactors && optimizerResult.winningFactors.length > 0 && (
        <div className="space-y-1.5">
          <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block">
            Winning Factors
          </span>
          <div className="space-y-0.5">
            {optimizerResult.winningFactors.map((f: string, i: number) => (
              <div key={i} className="flex items-start space-x-1.5">
                <span className="text-neon-purple text-[9px] shrink-0 mt-0.5">
                  {'›'}
                </span>
                <span className="font-sans text-[9.5px] text-white/55 leading-snug">{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Optimizer reasoning - only shown when genuinely available */}
      {optimizerResult.optimizerReasoning &&
        optimizerResult.optimizerReasoning.trim() !== '' && (
          <div className="border-t border-white/5 pt-2.5">
            <span className="font-mono text-[8px] text-white/30 uppercase tracking-widest block mb-1">
              Optimizer Reasoning
            </span>
            <p className="font-sans text-[9.5px] text-white/45 leading-relaxed italic">
              &ldquo;{optimizerResult.optimizerReasoning}&rdquo;
            </p>
          </div>
        )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ExplainabilityPanel - main export
// ---------------------------------------------------------------------------

export default function ExplainabilityPanel() {
  const { twinProfile, optimizerResult } = useNegotiationState();

  // Show panel content when at least one data source is present.
  // Each sub-panel handles its own missing-data state independently.
  const hasAnyData = twinProfile != null || optimizerResult != null;

  if (!hasAnyData) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[180px] space-y-3 py-8">
        <Brain className="h-8 w-8 text-white/10" />
        <div className="text-center px-4">
          <span className="font-mono text-[10px] text-white/30 uppercase tracking-widest block">
            AI Insight Pending
          </span>
          <p className="text-[10px] text-white/25 mt-1.5 max-w-[210px] mx-auto leading-relaxed">
            Select a product and begin a negotiation to activate the explainability layer.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 overflow-y-auto">
      {/* Customer Digital Twin */}
      <CollapsibleSection
        title="Customer Digital Twin"
        icon={<Brain className="h-3.5 w-3.5" />}
        accentClass="text-cyan-glow"
        bgClass="bg-cyan-glow/5"
        borderClass="border-cyan-glow/10"
        defaultOpen={true}
      >
        <DigitalTwinSubPanel />
      </CollapsibleSection>

      {/* Negotiation Intelligence */}
      <CollapsibleSection
        title="Negotiation Intelligence"
        icon={<Activity className="h-3.5 w-3.5" />}
        accentClass="text-neon-purple"
        bgClass="bg-neon-purple/5"
        borderClass="border-neon-purple/10"
        defaultOpen={true}
      >
        <NegotiationIntelligenceSubPanel />
      </CollapsibleSection>

      {/* Footer */}
      <div className="flex items-start space-x-1.5 px-0.5 pb-1">
        <Zap className="h-2.5 w-2.5 text-white/15 shrink-0 mt-0.5" />
        <span className="font-mono text-[7px] text-white/15 leading-relaxed uppercase tracking-wider">
          Read-only. Sourced from Ghost Negotiator internal reasoning.
          Zero negotiation behaviour altered.
        </span>
      </div>
    </div>
  );
}
