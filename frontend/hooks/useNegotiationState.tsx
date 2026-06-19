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
import { IS_DEMO_MODE, apiFetch, BACKEND_URL } from '../services/api';

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

  // Cart operations
  cart: any;
  inventoryStatus: string | null;
  nearMinimumPrice: boolean;
  lockCurrentDeal: () => Promise<void>;
  removeFromCart: (dealId: string) => Promise<void>;
  updateCartQuantity: (dealId: string, quantity: number) => Promise<void>;
  reopenNegotiation: (dealId: string) => Promise<void>;
  finalizePurchase: () => Promise<void>;
  loadCart: () => Promise<void>;
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
  const [customerId, setCustomerId] = useState<string>('U356787');  const [quantity, setQuantity] = useState<number>(1);

  const [isLoading, setIsLoading] = useState(true);
  const [isReplaying, setIsReplaying] = useState(false);
  const [playbackStep, setPlaybackStep] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  const playbackTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [cart, setCart] = useState<any>({
    items: [],
    summary: { total_items: 0, catalog_total: 0, negotiated_total: 0, total_savings: 0, average_savings_pct: 0 }
  });
  const [inventoryStatus, setInventoryStatus] = useState<string | null>(null);
  const [nearMinimumPrice, setNearMinimumPrice] = useState<boolean>(false);

  const loadCart = useCallback(async () => {
    if (IS_DEMO_MODE) return;
    try {
      const res = await apiFetch<any>(`/procurement/cart?customer_id=${customerId}`);
      if (res) {
        setCart(res);
      }
    } catch (err) {
      console.error("Failed to load cart", err);
    }
  }, [customerId]);

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
        await loadCart();
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

        let stock = 50;
        let minPrice = 0;
        try {
          const fullProd = await apiFetch<any>(`/products/${activeProd.id}`);
          if (fullProd) {
            stock = fullProd.stock_quantity;
            minPrice = fullProd.minimum_price;
          }
        } catch (e) {
          console.error("Failed to fetch product details for inventory status", e);
        }

        let invStatus = "Available";
        if (stock < 20) {
          invStatus = "Low Inventory";
        } else if (stock >= 100) {
          invStatus = "High Inventory";
        } else {
          invStatus = "Limited Availability";
        }
        setInventoryStatus(invStatus);

        // Compile DealSummary dynamically in memory from simulations and winner
        if (sims.length > 0 && opt) {
          const winningSim = sims.find(s => s.id === opt.winningStrategyId) || sims[0];
          const discountSim = sims.find(s => s.id === 's_discount');
          const discountPct = discountSim ? Math.round(discountSim.discountPercent ?? 0.0) : 15;

          const unitOffer = activeProd.price * (1.0 - (winningSim.discountPercent ?? 0.0) / 100.0);
          if (minPrice > 0 && unitOffer <= minPrice * 1.05) {
            setNearMinimumPrice(true);
          } else {
            setNearMinimumPrice(false);
          }

          const summary: DealSummary = {
            selectedProductId: activeProd.id,
            currentPrice: activeProd.price,
            customerDiscountRequest: discountPct,
            currentAiOfferPrice: unitOffer,
            bundleItems: winningSim.concessions || (winningSim.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : []),
            status: chatMsgs.length > 2 ? "Negotiation Active" : "Negotiation Initiated",
            closeProbability: winningSim.closeProbability,
            confidenceScore: opt.confidenceScore,
            optimizationObjective: currentMode
          };
          setDealSummary(summary);
          setSelectedStrategyId(opt.winningStrategyId);
        } else {
          setNearMinimumPrice(false);
          // Default summary if simulations are empty but product is selected
          const summary: DealSummary = {
            selectedProductId: activeProd.id,
            currentPrice: activeProd.price,
            customerDiscountRequest: 0,
            currentAiOfferPrice: activeProd.price,
            bundleItems: [],
            status: chatMsgs.length > 2 ? "Negotiation Active" : "Negotiation Initiated",
            closeProbability: 0.88,
            confidenceScore: 0.90,
            optimizationObjective: currentMode
          };
          setDealSummary(summary);
          setSelectedStrategyId(opt ? opt.winningStrategyId : 's_bundle');
        }
      }
    } catch (err) {
      console.error("Failed to load B2B negotiation details", err);
    } finally {
      setIsLoading(false);
    }
  }, [activeProduct, quantity, customerId, loadCart]);

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
            
            const winningSim = newSims.length > 0 ? (newSims.find(s => s.id === newWinner.winningStrategyId) || newSims[0]) : null;
            const discountSim = newSims.length > 0 ? newSims.find(s => s.id === 's_discount') : null;
            const discountPct = discountSim ? Math.round(discountSim.discountPercent ?? 0.0) : 15;
            const unitOffer = winningSim ? activeProduct.price * (1.0 - (winningSim.discountPercent ?? 0.0) / 100.0) : activeProduct.price;

            setDealSummary({
              selectedProductId: activeProduct.id,
              currentPrice: activeProduct.price,
              customerDiscountRequest: discountPct,
              currentAiOfferPrice: unitOffer,
              bundleItems: winningSim ? (winningSim.concessions || (winningSim.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : [])) : [],
              status: "Negotiation Active",
              closeProbability: winningSim ? winningSim.closeProbability : 0.88,
              confidenceScore: newWinner ? newWinner.confidenceScore : 0.90,
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
    
    if (IS_DEMO_MODE) {
      const prod = mockProducts.find(p => p.id === productId) || mockProducts[1];
      setActiveProduct(prod);
      stateManager.resetState(productId);
      await loadAllData(optimizationMode);
    } else {
      try {
        // Initialize negotiation by calling the new endpoint POST /api/v1/workspace/select-product
        const res = await apiFetch<any>('/workspace/select-product', {
          method: 'POST',
          body: JSON.stringify({
            customer_id: customerId,
            product_id: productId,
            quantity: quantity
          })
        });

        if (res && res.product) {
          const resolvedProd: Product = {
            id: res.product.id,
            name: res.product.name,
            description: res.product.description || "B2B catalog product under negotiation terms.",
            price: res.product.price,
            image: `/images/${res.product.id}.png`,
            category: res.product.category,
            specifications: res.product.specifications || {}
          };
          setActiveProduct(resolvedProd);
          
          if (res.deal_summary) {
            setDealSummary(res.deal_summary);
          }
          
          if (res.digital_twin) {
            setTwinProfile({
              priceSensitivity: Math.round((res.digital_twin.price_sensitivity ?? 0.5) * 100),
              urgency: Math.round((res.digital_twin.urgency ?? 0.5) * 100),
              riskAversion: Math.round((res.digital_twin.risk_aversion ?? 0.5) * 100),
              brandLoyalty: Math.round((res.digital_twin.brand_loyalty ?? 0.5) * 100),
              decisionSpeed: Math.round((res.digital_twin.decision_speed ?? 0.5) * 100),
              overallProfileScore: Math.round(((res.digital_twin.price_sensitivity + res.digital_twin.urgency + res.digital_twin.risk_aversion + res.digital_twin.brand_loyalty + res.digital_twin.decision_speed) / 5) * 100),
              personaName: "Calibrated Buyer",
              description: "Negotiation profile initialized from B2B catalog context."
            });
          }
          
          // Force a full reload of messages, twin profiles, history, and timeline events
          await loadAllData(optimizationMode, resolvedProd, quantity);
        }
      } catch (err) {
        console.error("Failed to select product and initialize workspace context", err);
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
      const chatRes = await submitMessage(text, customerId, activeProduct.id, quantity);
      if (chatRes) {
        if (chatRes.inventory_status) {
          setInventoryStatus(chatRes.inventory_status);
        }
        if (chatRes.near_minimum_price !== undefined) {
          setNearMinimumPrice(chatRes.near_minimum_price);
        }
      }
      
      // Reload everything from backend source of truth
      await loadAllData(optimizationMode);
    } catch (err) {
      console.error("Failed to submit chat message", err);
    } finally {
      setIsTyping(false);
      setTypingStatus('');
    }
  };

  const lockCurrentDeal = useCallback(async () => {
    if (IS_DEMO_MODE) return;
    if (!dealSummary || !activeProduct) return;
    try {
      const strategy = selectedStrategyId || 'balanced';
      const negotiated_price = dealSummary.currentAiOfferPrice;
      const concessions = dealSummary.bundleItems || [];
      const confidence_score = dealSummary.confidenceScore || 0.9;
      
      const response = await apiFetch<any>('/procurement/lock', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: customerId,
          product_id: activeProduct.id,
          quantity: quantity,
          negotiated_price,
          concessions,
          strategy,
          confidence_score
        })
      });
      if (response && response.status === 'success') {
        await loadCart();
      }
    } catch (err) {
      console.error("Failed to lock deal", err);
    }
  }, [customerId, activeProduct, quantity, dealSummary, selectedStrategyId, loadCart]);

  const removeFromCart = useCallback(async (dealId: string) => {
    if (IS_DEMO_MODE) return;
    try {
      await apiFetch<any>(`/procurement/cart/${dealId}`, {
        method: 'DELETE'
      });
      await loadCart();
    } catch (err) {
      console.error("Failed to remove from cart", err);
    }
  }, [loadCart]);

  const updateCartQuantity = useCallback(async (dealId: string, qty: number) => {
    if (IS_DEMO_MODE) return;
    try {
      await apiFetch<any>(`/procurement/cart/${dealId}/quantity`, {
        method: 'PUT',
        body: JSON.stringify({ quantity: qty })
      });
      await loadCart();
    } catch (err) {
      console.error("Failed to update cart quantity", err);
    }
  }, [loadCart]);

  const reopenNegotiation = useCallback(async (dealId: string) => {
    if (IS_DEMO_MODE) return;
    try {
      const res = await apiFetch<any>(`/procurement/cart/${dealId}/reopen`, {
        method: 'POST'
      });
      if (res && res.status === 'success') {
        await loadCart();
        await loadAllData(optimizationMode);
      }
    } catch (err) {
      console.error("Failed to reopen negotiation", err);
    }
  }, [loadCart, loadAllData, optimizationMode]);

  const finalizePurchase = useCallback(async () => {
    if (IS_DEMO_MODE) return;
    try {
      const res = await apiFetch<any>('/procurement/purchase', {
        method: 'POST',
        body: JSON.stringify({ customer_id: customerId })
      });
      if (res && res.status === 'success') {
        if (res.pdf_url) {
          const downloadUrl = `${BACKEND_URL.replace('/api/v1', '')}${res.pdf_url}`;
          window.open(downloadUrl, '_blank');
        }
        await loadCart();
        await loadAllData(optimizationMode);
      }
    } catch (err) {
      console.error("Failed to finalize purchase", err);
    }
  }, [customerId, loadCart, loadAllData, optimizationMode]);

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

  // Load initial product list and set defaults on mount if in integrated database mode
  useEffect(() => {
    if (!IS_DEMO_MODE) {
      const initDefaultProduct = async () => {
        try {
          await loadCart();
          const res = await apiFetch<any[]>('/products/search?q=');
          if (res && res.length > 0) {
            const firstProd = res[0];
            const firstProdId = firstProd.external_product_id || firstProd.id;
            await selectProduct(firstProdId);
          }
        } catch (err) {
          console.error("Failed to load initial product list", err);
        }
      };
      initDefaultProduct();
    }
  }, [loadCart]);

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
      refreshData,
      cart,
      inventoryStatus,
      nearMinimumPrice,
      lockCurrentDeal,
      removeFromCart,
      updateCartQuantity,
      reopenNegotiation,
      finalizePurchase,
      loadCart
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
