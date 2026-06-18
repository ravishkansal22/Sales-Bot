'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
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
import { getSimulations, getOptimizerResult, runRecalculation } from '../services/simulation';
import { getMessages, submitMessage, getTimelineEvents, getDealSummary } from '../services/customer';
import { getDigitalTwinProfile, getTwinHistory } from '../services/twin';
import { mockProducts } from '../mock/products';
import { stateManager } from '../services/stateManager';
import { IS_DEMO_MODE } from '../services/api';

interface NegotiationState {
  optimizationMode: OptimizationMode;
  setOptimizationMode: (mode: OptimizationMode) => void;
  selectedStrategyId: string | null;
  setSelectedStrategyId: (id: string | null) => void;
  simulations: SimulationOutput[];
  optimizerResult: OptimizerResult | null;
  twinProfile: DigitalTwinProfile | null;
  twinHistory: TwinHistoryPoint[];
  messages: Message[];
  timelineEvents: TimelineEvent[];
  
  // Workspace integration extensions
  activeProduct: Product;
  dealSummary: DealSummary | null;
  selectProduct: (productId: string) => Promise<void>;
  sendUserMessage: (text: string) => Promise<void>;
  isTyping: boolean;
  typingStatus: string;
  customerId: string;
  setCustomerId: (id: string) => void;
  quantity: number;
  setQuantity: (q: number) => void;

  // Playback Control System
  isReplaying: boolean;
  playbackStep: number; // 0: Idle, 1: Objection, 2: Twin Updated, 3: Strategies Generated, 4: Simulations Run, 5: Financials Evaluated, 6: Optimizer Selected Winner
  playbackSpeed: number; // 1 = 1x (3000ms per step), 2 = 2x (1500ms per step)
  setPlaybackSpeed: (speed: number) => void;
  triggerReplay: () => void;
  isLoading: boolean;
  refreshData: () => Promise<void>;
}

const NegotiationContext = createContext<NegotiationState | undefined>(undefined);

export function NegotiationProvider({ children }: { children: React.ReactNode }) {
  const [optimizationMode, setOptimizationMode] = useState<OptimizationMode>('balanced');
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>('s_bundle');
  const [simulations, setSimulations] = useState<SimulationOutput[]>([]);
  const [optimizerResult, setOptimizerResult] = useState<OptimizerResult | null>(null);
  const [twinProfile, setTwinProfile] = useState<DigitalTwinProfile | null>(null);
  const [twinHistory, setTwinHistory] = useState<TwinHistoryPoint[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  
  // Workspace states
  const [activeProduct, setActiveProduct] = useState<Product>(mockProducts[1]); // default elite
  const [dealSummary, setDealSummary] = useState<DealSummary | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [typingStatus, setTypingStatus] = useState('');
  const [customerId, setCustomerId] = useState<string>('cust_1');
  const [quantity, setQuantity] = useState<number>(1);

  const [isLoading, setIsLoading] = useState(true);
  const [isReplaying, setIsReplaying] = useState(false);
  const [playbackStep, setPlaybackStep] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  const playbackTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadAllData = useCallback(async (
    currentMode: OptimizationMode,
    prodOverride: Product | null = null,
    qtyOverride: number | null = null
  ) => {
    try {
      setIsLoading(true);
      const activeProd = prodOverride || activeProduct;
      const activeQty = qtyOverride || quantity;
      
      if (IS_DEMO_MODE) {
        stateManager.setOptimizationMode(currentMode);
        setActiveProduct(stateManager.getProduct());
        
        const [sims, opt, twin, history, chatMsgs, timeline, summary] = await Promise.all([
          getSimulations(currentMode, customerId),
          getOptimizerResult(currentMode, customerId),
          getDigitalTwinProfile(customerId),
          getTwinHistory(customerId),
          getMessages(customerId),
          getTimelineEvents(customerId),
          getDealSummary(customerId)
        ]);

        setSimulations(sims);
        setOptimizerResult(opt);
        setTwinProfile(twin);
        setTwinHistory(history);
        setMessages(chatMsgs);
        setTimelineEvents(timeline);
        setDealSummary(summary);
        
        if (opt) {
          setSelectedStrategyId(opt.winningStrategyId);
        }
      } else {
        // Fetch from database backend
        const [sims, opt, twin, history, chatMsgs, timeline] = await Promise.all([
          getSimulations(currentMode, customerId),
          getOptimizerResult(currentMode, customerId),
          getDigitalTwinProfile(customerId),
          getTwinHistory(customerId),
          getMessages(customerId),
          getTimelineEvents(customerId)
        ]);

        setSimulations(sims);
        setOptimizerResult(opt);
        setTwinProfile(twin);
        setTwinHistory(history);
        setMessages(chatMsgs);
        setTimelineEvents(timeline);

        // Compile DealSummary dynamically in memory from simulations and winner
        if (sims.length > 0 && opt) {
          const winningSim = sims.find(s => s.id === opt.winningStrategyId) || sims[0];
          const discountSim = sims.find(s => s.id === 's_discount');
          const discountPct = discountSim ? Math.round((1.0 - discountSim.marginRetention) * 100) : 15;

          const summary: DealSummary = {
            selectedProductId: activeProd.id,
            currentPrice: activeProd.price,
            customerDiscountRequest: discountPct,
            currentAiOfferPrice: winningSim.expectedProfit,
            bundleItems: winningSim.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : [],
            status: chatMsgs.length > 2 ? "Negotiation Active" : "Negotiation Initiated",
            closeProbability: winningSim.closeProbability,
            confidenceScore: opt.confidenceScore,
            optimizationObjective: currentMode
          };
          setDealSummary(summary);
          setSelectedStrategyId(opt.winningStrategyId);
        } else {
          setDealSummary(null);
        }
      }
    } catch (err) {
      console.error("Failed to load B2B negotiation details", err);
    } finally {
      setIsLoading(false);
    }
  }, [activeProduct, quantity, customerId]);

  // Sync mode changes to components
  useEffect(() => {
    if (!isReplaying) {
      if (!IS_DEMO_MODE && messages.length > 0) {
        // Recalculate simulation values dynamically on the backend when mode changes
        setIsLoading(true);
        const lastUserMsg = [...messages].reverse().find(m => m.sender === 'customer')?.text || `I want a cricket bat`;
        
        runRecalculation(customerId, activeProduct.id, quantity, lastUserMsg, optimizationMode)
          .then(({ simulations: newSims, winner: newWinner, digitalTwin: newTwin }) => {
            setSimulations(newSims);
            setOptimizerResult(newWinner);
            if (newWinner) {
              setSelectedStrategyId(newWinner.winningStrategyId);
            }
            
            const winningSim = newSims.find(s => s.id === newWinner.winningStrategyId) || newSims[0];
            const discountSim = newSims.find(s => s.id === 's_discount');
            const discountPct = discountSim ? Math.round((1.0 - discountSim.marginRetention) * 100) : 15;

            setDealSummary({
              selectedProductId: activeProduct.id,
              currentPrice: activeProduct.price,
              customerDiscountRequest: discountPct,
              currentAiOfferPrice: winningSim.expectedProfit,
              bundleItems: winningSim.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : [],
              status: "Negotiation Active",
              closeProbability: winningSim.closeProbability,
              confidenceScore: newWinner.confidenceScore,
              optimizationObjective: optimizationMode
            });
          })
          .catch(err => console.error("Failed to run recalculation", err))
          .finally(() => setIsLoading(false));
      } else {
        loadAllData(optimizationMode);
      }
    }
  }, [optimizationMode, loadAllData, isReplaying]);

  // Clean timer on unmount
  useEffect(() => {
    return () => {
      if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
    };
  }, []);

  // Product selector reset
  const selectProduct = async (productId: string) => {
    setIsLoading(true);
    
    // Resolve product details from local mockProducts list or backend
    const prod = mockProducts.find(p => p.id === productId) || mockProducts[1];
    setActiveProduct(prod);

    if (IS_DEMO_MODE) {
      stateManager.resetState(productId);
      await loadAllData(optimizationMode);
    } else {
      try {
        // Send welcome query to backend to bootstrap simulations and DB state
        const welcomeText = `I want to negotiate a B2B deal for ${prod.name}`;
        await submitMessage(welcomeText, customerId, prod.id, quantity);
        await loadAllData(optimizationMode, prod, quantity);
      } catch (err) {
        console.error("Failed to initialize product negotiation", err);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Chat message submit pipeline (Visualizing backend analysis stages)
  const sendUserMessage = async (text: string) => {
    if (!text.trim()) return;

    setIsTyping(true);
    
    // Add user message to UI immediately for fluid messaging
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [
      ...prev,
      { id: `temp_u_${Date.now()}`, sender: 'customer', text, timestamp: time }
    ]);

    try {
      // Step-by-step visual status tickers
      setTypingStatus("Analyzing customer intent...");
      await new Promise(resolve => setTimeout(resolve, 600));

      setTypingStatus("Calibrating Digital Twin...");
      await new Promise(resolve => setTimeout(resolve, 500));

      setTypingStatus("Evaluating 24 simulated futures...");
      await new Promise(resolve => setTimeout(resolve, 500));

      setTypingStatus("Generating optimal concessions...");
      
      // Submit user turn to backend
      await submitMessage(text, customerId, activeProduct.id, quantity);
      
      // Reload everything from backend source of truth
      await loadAllData(optimizationMode);
    } catch (err) {
      console.error("Failed to submit chat message", err);
    } finally {
      setIsTyping(false);
      setTypingStatus('');
    }
  };

  // Playback Control System
  const triggerReplay = useCallback(() => {
    if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
    
    setIsReplaying(true);
    setPlaybackStep(1);
    
    if (IS_DEMO_MODE) {
      stateManager.resetState(activeProduct.id);
    }

    // Load initial playback layout
    setTimelineEvents([{
      id: 't1',
      type: 'objection',
      timestamp: '10:15 AM',
      title: 'Objection Detected',
      description: 'Customer requested 30% discount, citing competitor offer from Willow-Core.',
      status: 'warning'
    }]);

    setTwinProfile(prev => prev ? {
      ...prev,
      priceSensitivity: 45,
      urgency: 30,
      riskAversion: 50,
      overallProfileScore: 50
    } : null);
    
    setSimulations([]);
    setOptimizerResult(null);
  }, [activeProduct]);

  useEffect(() => {
    if (!isReplaying) return;

    const delay = playbackSpeed === 2 ? 1500 : 3000;

    playbackTimerRef.current = setTimeout(async () => {
      const nextStep = playbackStep + 1;
      
      if (nextStep > 6) {
        setIsReplaying(false);
        setPlaybackStep(0);
        await loadAllData(optimizationMode);
        return;
      }

      setPlaybackStep(nextStep);

      // Fetch dynamic updates
      if (nextStep === 2) {
        setTwinProfile(prev => prev ? {
          ...prev,
          priceSensitivity: 95,
          urgency: 90,
          riskAversion: 65,
          overallProfileScore: 85
        } : null);
      } else if (nextStep === 3) {
        const sims = await getSimulations(optimizationMode, customerId);
        setSimulations(sims.slice(0, 2));
      } else if (nextStep === 4) {
        const sims = await getSimulations(optimizationMode, customerId);
        setSimulations(sims);
      } else if (nextStep === 5) {
        // Financials verified
      } else if (nextStep === 6) {
        const opt = await getOptimizerResult(optimizationMode, customerId);
        setOptimizerResult(opt);
        if (opt) {
          setSelectedStrategyId(opt.winningStrategyId);
        }
      }
    }, delay);

    return () => {
      if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
    };
  }, [isReplaying, playbackStep, playbackSpeed, optimizationMode, loadAllData, customerId]);

  const refreshData = async () => {
    await loadAllData(optimizationMode);
  };

  return (
    <NegotiationContext.Provider value={{
      optimizationMode,
      setOptimizationMode,
      selectedStrategyId,
      setSelectedStrategyId,
      simulations,
      optimizerResult,
      twinProfile,
      twinHistory,
      messages,
      timelineEvents,
      activeProduct,
      dealSummary,
      selectProduct,
      sendUserMessage,
      isTyping,
      typingStatus,
      customerId,
      setCustomerId,
      quantity,
      setQuantity,
      isReplaying,
      playbackStep,
      playbackSpeed,
      setPlaybackSpeed,
      triggerReplay,
      isLoading,
      refreshData
    }}>
      {children}
    </NegotiationContext.Provider>
  );
}

export function useNegotiationState() {
  const context = useContext(NegotiationContext);
  if (!context) {
    throw new Error('useNegotiationState must be used within a NegotiationProvider');
  }
  return context;
}
