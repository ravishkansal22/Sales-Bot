export type OptimizationMode = 'balanced' | 'max_profit' | 'max_margin' | 'max_close_rate';

export interface DigitalTwinProfile {
  priceSensitivity: number; // 0 - 100
  urgency: number;          // 0 - 100
  riskAversion: number;     // 0 - 100
  brandLoyalty: number;     // 0 - 100
  decisionSpeed: number;    // 0 - 100
  overallProfileScore: number; // 0 - 100
  personaName: string;
  description: string;
}

export interface SimulationRollout {
  id: string;
  stepName: string;
  customerReaction: string;
  timelineEvents: string[];
  risk: 'LOW' | 'MEDIUM' | 'HIGH';
  outcome: string;
}

export interface SimulationOutput {
  id: string;
  name: string;
  description: string;
  closeProbability: number; // 0.0 - 1.0
  riskScore: number;        // 0 - 100
  expectedProfit: number;   // In dollars
  expectedValue: number;    // In dollars
  marginRetention: number;  // 0.0 - 1.0
  confidenceScore: number;  // 0.0 - 1.0
  discountPercent?: number;  // 0.0 - 100.0
  rollouts: SimulationRollout[];
  concessions?: string[];
}

export interface OptimizerResult {
  winningStrategyId: string;
  optimizationMode: OptimizationMode;
  confidenceScore: number;
  winningFactors: string[];
  optimizerReasoning: string;
}

export interface Message {
  id: string;
  sender: 'customer' | 'company';
  text: string;
  timestamp: string;
  recommended_products?: Product[];
  intent_type?: string;
  comparison_results?: any;
}

export interface TimelineEvent {
  id: string;
  type: 'objection' | 'price' | 'urgency' | 'strategy' | 'simulation' | 'optimizer';
  timestamp: string;
  title: string;
  description: string;
  status: 'warning' | 'info' | 'success';
}

export interface TwinHistoryPoint {
  timestamp: string;
  priceSensitivity: number;
  urgency: number;
  riskAversion: number;
  brandLoyalty: number;
  decisionSpeed: number;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  image: string;
  category: string;
  specifications: Record<string, string>;
}

export interface DealSummary {
  selectedProductId: string | null;
  currentPrice: number;
  customerDiscountRequest: number; // e.g. 15 for 15%
  currentAiOfferPrice: number;
  bundleItems: string[];
  status: string;
  closeProbability: number;
  confidenceScore: number;
  optimizationObjective: string;
}

