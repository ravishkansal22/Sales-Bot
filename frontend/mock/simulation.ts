import { SimulationOutput, OptimizerResult, OptimizationMode } from '../types/api';

export const mockStrategies: SimulationOutput[] = [
  {
    id: 's_discount',
    name: 'Discount Strategy',
    description: 'Provide an immediate 30% price reduction to match the customer request of $105,000.',
    closeProbability: 0.92,
    riskScore: 65,
    expectedProfit: 105000,
    expectedValue: 96600,
    marginRetention: 0.70,
    confidenceScore: 0.95,
    rollouts: [
      {
        id: 'r_d1',
        stepName: 'Step 1: Offer $105k Flat',
        customerReaction: 'LogiCore procurement immediately approves. Budget pressures are relieved.',
        timelineEvents: ['Price target matched', 'Procurement sign-off'],
        risk: 'LOW',
        outcome: 'Deal closes within 24 hours.'
      },
      {
        id: 'r_d2',
        stepName: 'Step 2: SLA Upgrade Demand',
        customerReaction: 'Customer accepts price but continues to push for 99.99% SLA inclusion.',
        timelineEvents: ['SLA escalation', 'Legal review required'],
        risk: 'MEDIUM',
        outcome: 'Contract execution delayed by 5 days; support margin decreases.'
      },
      {
        id: 'r_d3',
        stepName: 'Step 3: Future Renegotiations',
        customerReaction: 'Establishes a low baseline price. Next renewal starts at a heavily discounted point.',
        timelineEvents: ['Baseline reset', 'Margin erosion'],
        risk: 'HIGH',
        outcome: 'High customer churn risk at next renewal if we attempt price correction.'
      }
    ]
  },
  {
    id: 's_hardline',
    name: 'Hardline Strategy',
    description: 'Reject discount request. Maintain original renewal price of $150,000, emphasizing migration friction.',
    closeProbability: 0.25,
    riskScore: 90,
    expectedProfit: 150000,
    expectedValue: 37500,
    marginRetention: 1.00,
    confidenceScore: 0.75,
    rollouts: [
      {
        id: 'r_h1',
        stepName: 'Step 1: Issue Flat Renewal Notice',
        customerReaction: 'LogiCore champion escalates to VP. Stiff pushback on budget variance.',
        timelineEvents: ['Executive escalation', 'Pricing deadlock'],
        risk: 'HIGH',
        outcome: 'Negotiations stall; customer requests database export tools.'
      },
      {
        id: 'r_h2',
        stepName: 'Step 2: Competitor Pilot Launch',
        customerReaction: 'LogiCore begins live trial with SaaS-Metrics. IT starts testing migration scripts.',
        timelineEvents: ['Competitor trial active', 'Migration planning'],
        risk: 'HIGH',
        outcome: 'Probability of close drops below 15%.'
      },
      {
        id: 'r_h3',
        stepName: 'Step 3: Churn Event',
        customerReaction: 'CFO signs contract with SaaS-Metrics. LogiCore churns.',
        timelineEvents: ['Contract termination', 'Account churn'],
        risk: 'HIGH',
        outcome: 'Loss of $150k ARR; negative PR within logistics sector.'
      }
    ]
  },
  {
    id: 's_bundle',
    name: 'Value Bundle Strategy',
    description: 'Offer a minor discount to $130,000, but include premium SLA (99.99%) and 2 developer training credits.',
    closeProbability: 0.88,
    riskScore: 25,
    expectedProfit: 130000,
    expectedValue: 114400,
    marginRetention: 0.82,
    confidenceScore: 0.90,
    rollouts: [
      {
        id: 'r_b1',
        stepName: 'Step 1: Pitch Bundled Value Package',
        customerReaction: 'LogiCore champion welcomes SLA inclusion. CFO agrees to review value justification.',
        timelineEvents: ['Value pitch received', 'CFO review'],
        risk: 'LOW',
        outcome: 'SaaS-Metrics threat neutralized due to high migration friction vs value additions.'
      },
      {
        id: 'r_b2',
        stepName: 'Step 2: Engineering SLA Alignment',
        customerReaction: 'Platform team confirms SLA compliance with existing infrastructure.',
        timelineEvents: ['SLA audit success', 'Legal approval'],
        risk: 'LOW',
        outcome: 'Uptime guarantees locked into new Master Service Agreement.'
      },
      {
        id: 'r_b3',
        stepName: 'Step 3: Contract Ratification',
        customerReaction: 'LogiCore signs 1-year bundle agreement at $130,000.',
        timelineEvents: ['Contract signed', 'Upsell training active'],
        risk: 'LOW',
        outcome: 'Locked in $130k ARR with healthy 82% margin and expanded feature adoption.'
      }
    ]
  },
  {
    id: 's_personalized',
    name: 'Personalized Multi-Year Term',
    description: 'Lock in a 3-year term commitment at $120,000/year, billed semi-annually, with standard SLA.',
    closeProbability: 0.80,
    riskScore: 30,
    expectedProfit: 360000, // $120k * 3
    expectedValue: 288000,  // closeProbability * expectedProfit
    marginRetention: 0.94,  // High margins over time due to low servicing overhead
    confidenceScore: 0.88,
    rollouts: [
      {
        id: 'r_p1',
        stepName: 'Step 1: Pitch Multi-Year Cost Security',
        customerReaction: 'VP likes long-term budget stability. Procurement requests semi-annual payment schedule.',
        timelineEvents: ['Multi-year proposal', 'Procurement negotiation'],
        risk: 'LOW',
        outcome: 'Budget approvals shifted to capital expenditure, bypassing Q3 operating budget restrictions.'
      },
      {
        id: 'r_p2',
        stepName: 'Step 2: Legal Term Review',
        customerReaction: 'Minor updates to standard exit clauses for convenience, demanding 90 days notice.',
        timelineEvents: ['Exit clause audit', 'Redlining process'],
        risk: 'MEDIUM',
        outcome: 'Clauses agreed with a reciprocal termination provision.'
      },
      {
        id: 'r_p3',
        stepName: 'Step 3: Account Lockin',
        customerReaction: 'LogiCore signs 3-year contract. Lifetime value triples.',
        timelineEvents: ['3-year contract signed', 'LTV expansion'],
        risk: 'LOW',
        outcome: 'ARR locked for 36 months, eliminating competitor threat entirely.'
      }
    ]
  }
];

export const mockOptimizerResults: Record<OptimizationMode, OptimizerResult> = {
  balanced: {
    winningStrategyId: 's_bundle',
    optimizationMode: 'balanced',
    confidenceScore: 0.90,
    winningFactors: [
      'Neutralizes competitor SaaS-Metrics thread by matching SLA demand.',
      'Saves 12% margin compared to pure discount strategy.',
      'Includes training credits to drive user adoption and reduce support load.'
    ],
    optimizerReasoning: 'Under Balanced mode, the Value Bundle Strategy represents the optimal risk-to-reward ratio. It secures a high probability of close (88%) while maintaining an 82% margin retention, neutralizing competitor leverage with minimal pricing concessions.'
  },
  max_profit: {
    winningStrategyId: 's_personalized',
    optimizationMode: 'max_profit',
    confidenceScore: 0.85,
    winningFactors: [
      'Triples lifetime contract value (LTV) to $360,000.',
      'Maintains pricing integrity near the target line ($120k/year).',
      'Provides high long-term revenue predictability.'
    ],
    optimizerReasoning: 'Under Max Profit mode, locking the customer into a 3-year contract at $120,000/year yields the highest total contract profit ($360k total) with high confidence (85%). This strategy avoids flat pricing collapse while maximizing long-term cash flow.'
  },
  max_margin: {
    winningStrategyId: 's_personalized',
    optimizationMode: 'max_margin',
    confidenceScore: 0.88,
    winningFactors: [
      'Reaches a peak margin retention rate of 94%.',
      'Amortizes setup costs over a 36-month timeline.',
      'Eliminates annual renewal administrative overhead.'
    ],
    optimizerReasoning: 'Under Max Margin mode, the Personalized Multi-Year Term is selected because it delivers a 94% margin retention rate. Spreading infrastructure support costs across a 3-year horizon optimizes service delivery efficiency.'
  },
  max_close_rate: {
    winningStrategyId: 's_discount',
    optimizationMode: 'max_close_rate',
    confidenceScore: 0.95,
    winningFactors: [
      'Achieves highest close probability at 92%.',
      'Meets customer exact CFO request of $105,000 renewals.',
      'Requires zero administrative or SLA exceptions.'
    ],
    optimizerReasoning: 'Under Max Close Rate mode, the Discount Strategy is chosen despite margin erosion. The engine estimates a 92% probability of closing before the Q3 renewal deadline, eliminating immediate churn risk.'
  }
};
