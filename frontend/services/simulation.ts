import { IS_DEMO_MODE, apiFetch } from './api';
import { stateManager } from './stateManager';
import { SimulationOutput, OptimizerResult, OptimizationMode, DigitalTwinProfile } from '../types/api';

// Helper to map backend strategy results to frontend SimulationOutput schema
export function mapBackendSimulations(backendSims: any[]): SimulationOutput[] {
  return backendSims.map(s => {
    const offerType = s.offer_type || 'discount';
    // Map strategy name to mock id structure s_xxxx
    const id = s.strategy_name ? (s.strategy_name.startsWith('s_') ? s.strategy_name : `s_${s.strategy_name}`) : `s_${offerType}`;
    
    return {
      id,
      name: s.strategy_name || 'Strategy',
      description: s.reasoning || 'No details provided.',
      closeProbability: s.average_close_probability ?? 0.5,
      riskScore: Math.round((s.average_risk_score ?? 0.2) * 100),
      expectedProfit: s.average_expected_profit ?? 0.0,
      expectedValue: s.average_expected_value ?? 0.0,
      marginRetention: s.average_gross_margin_retention ?? 1.0,
      confidenceScore: s.confidence_score ?? 0.8,
      discountPercent: s.discount_percent ?? 0.0,
      concessions: s.concessions || [],
      rollouts: (s.rollouts || []).map((r: any, idx: number) => {
        let risk: 'LOW' | 'MEDIUM' | 'HIGH' = 'LOW';
        if (r.risk_score > 0.6) risk = 'HIGH';
        else if (r.risk_score > 0.3) risk = 'MEDIUM';
        
        return {
          id: r.rollout_id || `r_${idx}`,
          stepName: `Rollout Step ${idx + 1}`,
          customerReaction: r.customer_reaction?.simulated_response || r.reasoning || 'No reaction',
          timelineEvents: r.timeline_events || [],
          risk,
          outcome: r.customer_reaction?.simulated_response || r.reasoning || 'Completed'
        };
      })
    };
  });
}

// Helper to map backend winner to frontend OptimizerResult
export function mapBackendOptimizerResult(winner: any): OptimizerResult {
  return {
    winningStrategyId: `s_${winner.winning_strategy || 'discount'}`,
    optimizationMode: (winner.optimization_mode || 'balanced') as OptimizationMode,
    confidenceScore: winner.confidence_score ?? 0.8,
    winningFactors: winner.winning_factors || ['Highest expected value'],
    optimizerReasoning: winner.optimizer_reasoning || 'Selected as the most balanced option based on simulated expected profit and risk.',
    currentDiscountPercent: winner.current_discount_percent !== undefined ? winner.current_discount_percent : winner.actual_offer_discount,
    currentOfferPrice: winner.current_offer_price !== undefined ? winner.current_offer_price : winner.actual_offer_price,
    // negotiated_quantity is the authoritative backend quantity for this negotiation session.
    // The frontend must sync its quantity state to this value after every loadAllData call.
    negotiatedQuantity: typeof winner.negotiated_quantity === 'number' ? winner.negotiated_quantity : undefined,
    // allRankings is optional — used only by the read-only Explainability panel.
    // Never influences negotiation logic or strategy selection.
    allRankings: Array.isArray(winner.all_rankings) ? winner.all_rankings : undefined,
  };
}

export async function getSimulations(mode: OptimizationMode, customerId: string): Promise<SimulationOutput[]> {
  if (IS_DEMO_MODE) {
    return stateManager.getSimulations();
  }

  const data = await apiFetch<any[]>(`/customers/${customerId}/simulations`);
  return mapBackendSimulations(data);
}

export async function getOptimizerResult(mode: OptimizationMode, customerId: string): Promise<OptimizerResult> {
  if (IS_DEMO_MODE) {
    return stateManager.getOptimizerResult();
  }

  const data = await apiFetch<any>(`/customers/${customerId}/optimizer-result`);
  if (!data) {
    // Return empty fallback
    return {
      winningStrategyId: 's_bundle',
      optimizationMode: mode,
      confidenceScore: 0.5,
      winningFactors: ['Loading...'],
      optimizerReasoning: 'Connecting optimizer telemetry...'
    };
  }
  return mapBackendOptimizerResult(data);
}

export async function runRecalculation(
  customerId: string,
  productId: string,
  quantity: number,
  message: string,
  mode: OptimizationMode
): Promise<{ simulations: SimulationOutput[]; winner: OptimizerResult; digitalTwin: any }> {
  const data = await apiFetch<any>('/simulate', {
    method: 'POST',
    body: JSON.stringify({
      message,
      customer_id: customerId,
      product_id: productId,
      quantity,
      optimization_mode: mode
    })
  });

  return {
    simulations: mapBackendSimulations(data.simulations),
    winner: mapBackendOptimizerResult(data.winner),
    digitalTwin: data.digital_twin
  };
}
