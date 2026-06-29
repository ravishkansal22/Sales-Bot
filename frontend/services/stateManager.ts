import { 
  OptimizationMode, 
  SimulationOutput, 
  OptimizerResult, 
  DigitalTwinProfile, 
  TwinHistoryPoint, 
  Message, 
  TimelineEvent, 
  Product, 
  DealSummary 
} from '../types/api';
import { mockProducts } from '../mock/products';
import { mockStrategies, mockOptimizerResults } from '../mock/simulation';

// Simulated B2B Backend State
class BackendStateManager {
  private activeProduct: Product = mockProducts[1]; // Default to Elite
  private optimizationMode: OptimizationMode = 'balanced';
  private messages: Message[] = [];
  
  // Deal summary metrics
  private discountRequest = 0;
  private currentAiOffer = 6999;
  private bundleItems: string[] = [];
  private status = 'Awaiting Selection';
  private closeProb = 0.88;
  
  // Twin profile parameters
  private twinProfile: DigitalTwinProfile = {
    priceSensitivity: 55,
    urgency: 50,
    riskAversion: 55,
    brandLoyalty: 75,
    decisionSpeed: 50,
    overallProfileScore: 65,
    personaName: 'Moderate-Urgency Standard Buyer',
    description: 'Procurement is looking at standard English Willow options. Brand value is high but they expect standard concessions.'
  };

  private timelineEvents: TimelineEvent[] = [];

  constructor() {
    this.resetState(this.activeProduct.id);
  }

  public resetState(productId: string) {
    const prod = mockProducts.find(p => p.id === productId) || mockProducts[1];
    this.activeProduct = prod;
    this.discountRequest = 0;
    this.currentAiOffer = prod.price;
    this.bundleItems = [];
    this.status = 'Negotiation Initiated';
    this.closeProb = 0.88;
    this.optimizationMode = 'balanced';
    
    // Initial Twin State
    this.twinProfile = {
      priceSensitivity: 45,
      urgency: 35,
      riskAversion: 50,
      brandLoyalty: 80,
      decisionSpeed: 45,
      overallProfileScore: 70,
      personaName: 'Standard Brand Loyalist',
      description: `Negotiating contract supply for ${prod.name}. The buyer prefers our high-grade materials but has standard budgetary constraints.`
    };

    // Welcome message
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    this.messages = [
      {
        id: 'msg_welcome',
        sender: 'company',
        text: `Welcome. We are evaluating a B2B agreement for ${prod.name} (Listed Price: ₹${prod.price.toLocaleString()}). I am calibrated to negotiate bundles, custom terms, or discount requests. How would you like to proceed?`,
        timestamp: time
      }
    ];

    // Initial timeline
    this.timelineEvents = [
      {
        id: 'init_t1',
        type: 'strategy',
        timestamp: time,
        title: 'Deal Initialized',
        description: `B2B supply profile loaded for ${prod.name}. List Price: ₹${prod.price.toLocaleString()}.`,
        status: 'info'
      }
    ];
  }

  public getProduct(): Product {
    return this.activeProduct;
  }

  public getMessages(): Message[] {
    return this.messages;
  }

  public getTwinProfile(): DigitalTwinProfile {
    return this.twinProfile;
  }

  public getTimelineEvents(): TimelineEvent[] {
    return this.timelineEvents;
  }

  public getDealSummary(): DealSummary {
    const winner = this.getOptimizerResult();
    return {
      selectedProductId: this.activeProduct.id,
      currentPrice: this.activeProduct.price,
      customerDiscountRequest: this.discountRequest,
      currentAiOfferPrice: this.currentAiOffer,
      quantity: 1, // Demo state manager default quantity is 1
      bundleItems: this.bundleItems,
      status: this.status,
      closeProbability: this.closeProb,
      confidenceScore: winner.confidenceScore,
      optimizationObjective: this.optimizationMode
    };
  }

  public setOptimizationMode(mode: OptimizationMode) {
    this.optimizationMode = mode;
    
    // Changing optimization mode dynamically updates close probabilities and status based on winner
    const winner = this.getOptimizerResult();
    const strategy = this.getSimulations().find(s => s.id === winner.winningStrategyId);
    
    if (strategy) {
      this.closeProb = strategy.closeProbability;
      
      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      this.timelineEvents.push({
        id: `mode_chg_${Date.now()}`,
        type: 'optimizer',
        timestamp: time,
        title: `Optimizer Objective Updated`,
        description: `Recalculated strategy with objective: ${mode.replace('_', ' ').toUpperCase()}. Selected Winner: ${strategy.name}.`,
        status: 'success'
      });
    }
  }

  public getOptimizationMode(): OptimizationMode {
    return this.optimizationMode;
  }

  // Returns simulations adjusted by twin metrics to show reactive recalculations
  public getSimulations(): SimulationOutput[] {
    const sensitivity = this.twinProfile.priceSensitivity;
    
    // Scale expectation value and probability depending on twin profile
    return mockStrategies.map(strat => {
      let closeProbability = strat.closeProbability;
      let expectedProfit = strat.expectedProfit;
      let description = strat.description;
      
      if (strat.id === 's_discount') {
        // High price sensitivity makes discount close rate go up
        closeProbability = Math.min(0.98, strat.closeProbability + (sensitivity - 50) * 0.002);
        expectedProfit = this.activeProduct.price * 0.7; // 30% off
        description = `Provide an immediate 30% price reduction to match the customer request of ₹${expectedProfit.toLocaleString()}.`;
      } else if (strat.id === 's_hardline') {
        // High sensitivity makes hardline close rate plummet
        closeProbability = Math.max(0.05, strat.closeProbability - (sensitivity - 50) * 0.004);
        expectedProfit = this.activeProduct.price;
        description = `Reject discount request. Maintain original price of ₹${expectedProfit.toLocaleString()}, emphasizing manufacturing craftsmanship.`;
      } else if (strat.id === 's_bundle') {
        closeProbability = Math.min(0.95, strat.closeProbability + (sensitivity - 50) * 0.001);
        expectedProfit = this.activeProduct.price * 0.85; // 15% off
        description = `Offer a minor discount to ₹${expectedProfit.toLocaleString()} and package free grips and batting covers.`;
      } else if (strat.id === 's_personalized') {
        expectedProfit = this.activeProduct.price * 0.8 * 3; // 3 year contract
        description = `Secure a 3-year supply agreement at ₹${(this.activeProduct.price * 0.8).toLocaleString()}/year.`;
      }

      return {
        ...strat,
        closeProbability,
        expectedProfit,
        description,
        expectedValue: closeProbability * expectedProfit,
        marginRetention: strat.id === 's_discount' ? 0.7 : strat.id === 's_hardline' ? 1.0 : strat.id === 's_bundle' ? 0.82 : 0.94
      };
    });
  }

  // Retrieve active optimizer decision
  public getOptimizerResult(): OptimizerResult {
    const baseResult = mockOptimizerResults[this.optimizationMode];
    let winningId = baseResult.winningStrategyId;
    
    // If sensitivity is extremely high and mode is Balanced, winner shifts from Bundle to Discount
    if (this.twinProfile.priceSensitivity > 80 && this.optimizationMode === 'balanced') {
      winningId = 's_discount';
    }

    return {
      ...baseResult,
      winningStrategyId: winningId,
      optimizerReasoning: this.twinProfile.priceSensitivity > 80 
        ? `Given the customer's high Price Sensitivity (${this.twinProfile.priceSensitivity}/100) and competitor pressure, the engine recommends pivoting to the Discount or Bundle Strategy to preserve market share, accepting margin dilution.`
        : baseResult.optimizerReasoning
    };
  }

  // Processes B2B customer chat messages and generates replies, simulating the backend logic
  public async processMessageEvent(userText: string): Promise<void> {
    const text = userText.toLowerCase();
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const timestamp = time;

    // Add user message
    this.messages.push({
      id: `msg_u_${Date.now()}`,
      sender: 'customer',
      text: userText,
      timestamp
    });

    // Simulated network processing delay
    await new Promise(resolve => setTimeout(resolve, 800));

    // Dynamic state updates based on content keywords (Backend Analysis)
    if (text.includes('competitor') || text.includes('cheaper') || text.includes('willow') || text.includes('saas')) {
      // Competitor threat detected
      this.twinProfile.priceSensitivity = 95;
      this.twinProfile.brandLoyalty = 20;
      this.twinProfile.urgency = 90;
      this.twinProfile.overallProfileScore = 85;
      this.twinProfile.personaName = 'Price-Sensitive Competitor Threat';
      this.twinProfile.description = 'Buyer is actively weaponizing a cheaper competitor proposal from Willow-Core. High risk of churn. Pricing concessions required to secure deal.';
      
      this.discountRequest = 30;
      this.currentAiOffer = Math.round(this.activeProduct.price * 0.85); // 15% discount
      this.bundleItems = ['Free Dynamic Rubber Grip', 'Heavy-duty Batting Cover'];
      this.status = 'Competitor Threat Active';
      this.closeProb = 0.88;

      this.messages.push({
        id: `msg_ai_${Date.now()}`,
        sender: 'company',
        text: `We recognize that competitor brands like Willow-Core offer lower list prices. However, our bats are crafted with Grade A select willow, offering superior ping velocity and structural longevity. To bridge the variance, under Balanced optimization, we can structure a Value Bundle: we'll lower unit costs to ₹${this.currentAiOffer.toLocaleString()} and include our premium grip and padded cover at no additional charge.`,
        timestamp
      });

      this.timelineEvents.push(
        {
          id: `t_comp_${Date.now()}`,
          type: 'objection',
          timestamp,
          title: 'Competitor Threat Detected',
          description: 'Buyer referenced Willow-Core pricing. Twin price sensitivity spiked to 95/100.',
          status: 'warning'
        },
        {
          id: `t_twin_${Date.now()}`,
          type: 'price',
          timestamp,
          title: 'Digital Twin Recalibrated',
          description: 'Brand loyalty index reduced to 20/100. Close probabilities updated.',
          status: 'info'
        }
      );
    } 
    else if (text.includes('discount') || text.includes('price') || text.includes('%') || text.includes('off')) {
      // Discount request
      this.twinProfile.priceSensitivity = 85;
      this.twinProfile.brandLoyalty = 50;
      this.twinProfile.personaName = 'Aggressive Price Negotiator';
      
      // Try to extract numbers, default to 15%
      const match = text.match(/\d+/);
      const reqPct = match ? parseInt(match[0]) : 15;
      this.discountRequest = reqPct;
      
      const concession = reqPct >= 20 ? 0.88 : 0.92; // give 8% or 12% off
      this.currentAiOffer = Math.round(this.activeProduct.price * concession);
      this.bundleItems = [];
      this.status = 'Price Concession Offered';
      this.closeProb = 0.92;

      this.messages.push({
        id: `msg_ai_${Date.now()}`,
        sender: 'company',
        text: `A ${reqPct}% price concession has been simulated against our revenue models. To preserve target margins, we cannot fully match ${reqPct}%, but we can offer a calibrated price of ₹${this.currentAiOffer.toLocaleString()} (saving you ₹${(this.activeProduct.price - this.currentAiOffer).toLocaleString()} per unit) with standard delivery SLA.`,
        timestamp
      });

      this.timelineEvents.push({
        id: `t_disc_${Date.now()}`,
        type: 'price',
        timestamp,
        title: 'Objection Detected: Price Concession',
        description: `Customer requested ${reqPct}% off. Calibrated offer set to ₹${this.currentAiOffer.toLocaleString()}.`,
        status: 'warning'
      });
    } 
    else if (text.includes('bundle') || text.includes('accessory') || text.includes('accessories') || text.includes('grip')) {
      // Bundle request
      this.twinProfile.urgency = 75;
      this.twinProfile.riskAversion = 80;
      
      this.discountRequest = 5;
      this.currentAiOffer = this.activeProduct.price;
      this.bundleItems = ['Octopus Cushioned Grip', 'Dynamic Anti-scuff Sheet'];
      this.status = 'Bundle Option Prepared';
      this.closeProb = 0.85;

      this.messages.push({
        id: `msg_ai_${Date.now()}`,
        sender: 'company',
        text: `To avoid price erosion, we can maintain the listing value of ₹${this.activeProduct.price.toLocaleString()} but package our premium Octopus Cushioned Grip and Anti-scuff protection sheet (valued at ₹1,500) within the standard B2B agreement.`,
        timestamp
      });

      this.timelineEvents.push({
        id: `t_bund_${Date.now()}`,
        type: 'strategy',
        timestamp,
        title: 'Value Bundle Simulated',
        description: 'Customer values add-ons. Concession structured as accessories bundle.',
        status: 'info'
      });
    } 
    else if (text.includes('accept') || text.includes('agree') || text.includes('deal') || text.includes('final') || text.includes('buy')) {
      // Deal ratified
      this.status = 'Deal Concluded';
      this.closeProb = 1.0;
      this.twinProfile.overallProfileScore = 98;
      
      this.messages.push({
        id: `msg_ai_${Date.now()}`,
        sender: 'company',
        text: `Deal finalized! We have locked in the supply agreement for ${this.activeProduct.name} at ₹${this.currentAiOffer.toLocaleString()}/unit with the following bundles: ${this.bundleItems.length > 0 ? this.bundleItems.join(', ') : 'None'}. Generating B2B contract for execution.`,
        timestamp
      });

      this.timelineEvents.push({
        id: `t_rat_${Date.now()}`,
        type: 'simulation',
        timestamp,
        title: 'Contract Closed Successfully',
        description: `Deal signed at ₹${this.currentAiOffer.toLocaleString()}. Overall yield optimized.`,
        status: 'success'
      });
    } 
    else {
      // Default
      this.messages.push({
        id: `msg_ai_${Date.now()}`,
        sender: 'company',
        text: `Understood. I am running simulated negotiation futures based on this input. Let me know if you would like to discuss price discounts, bundled items, or comparison matrices against competitor brands.`,
        timestamp
      });

      this.timelineEvents.push({
        id: `t_default_${Date.now()}`,
        type: 'simulation',
        timestamp,
        title: 'Scenario Simulation Swept',
        description: 'Evaluated alternative concession paths. Strategy outputs stable.',
        status: 'info'
      });
    }
  }
}

// Singleton state manager
export const stateManager = new BackendStateManager();
export default stateManager;
