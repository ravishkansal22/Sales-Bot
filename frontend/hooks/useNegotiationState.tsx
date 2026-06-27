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
  activeProduct: Product | null;
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

const mergeById = (existing: Message[], history: Message[]): Message[] => {
  const mergedMap = new Map<string, Message>();

  const addMessageToMap = (msg: Message) => {
    mergedMap.set(msg.id, msg);
    if (msg.client_message_id) {
      mergedMap.set(msg.client_message_id, msg);
    }
  };

  existing.forEach(msg => {
    addMessageToMap({ ...msg });
  });

  history.forEach(msg => {
    let existingMatch = mergedMap.get(msg.id);
    if (!existingMatch && msg.client_message_id) {
      existingMatch = mergedMap.get(msg.client_message_id);
    }

    if (existingMatch) {
      const reconciled = {
        ...existingMatch,
        ...msg,
        status: "sent"
      };
      if (existingMatch.id !== reconciled.id) {
        mergedMap.delete(existingMatch.id);
      }
      if (existingMatch.client_message_id && existingMatch.client_message_id !== reconciled.client_message_id) {
        mergedMap.delete(existingMatch.client_message_id);
      }
      addMessageToMap(reconciled);
    } else {
      addMessageToMap({
        ...msg,
        status: "sent"
      });
    }
  });

  const uniqueMessages = Array.from(new Set(mergedMap.values()));

  return uniqueMessages.sort((a, b) => {
    if (a.created_at && b.created_at) {
      const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      if (diff !== 0) return diff;
    }
    if (a.sender !== b.sender) {
      return a.sender === 'customer' ? -1 : 1;
    }
    return 0;
  });
};

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
  const [activeProduct, setActiveProduct] = useState<Product | null>(() => {
    if (IS_DEMO_MODE) {
      return mockProducts[1];
    }
    return null;
  });
  const activeProductRef = useRef<Product | null>(activeProduct);
  useEffect(() => {
    activeProductRef.current = activeProduct;
  }, [activeProduct]);

  const prevModeRef = useRef<OptimizationMode>(optimizationMode);

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
      setCart({
        items: [],
        summary: { total_items: 0, catalog_total: 0, negotiated_total: 0, total_savings: 0, average_savings_pct: 0 }
      });
    }
  }, [customerId]);

  const loadAllData = useCallback(async (
    currentMode: OptimizationMode,
    prodOverride: Product | null = null,
    qtyOverride: number | null = null,
    overwrite: boolean = false
  ) => {
    try {
      setIsLoading(true);
      const activeProd = prodOverride || activeProductRef.current;
      if (!activeProd) {
        setIsLoading(false);
        return;
      }
      // Initial quantity fallback — the live-mode branch overwrites this from the backend.
      const qtyFallback = qtyOverride ?? quantity;
      
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
        if (overwrite) {
          setMessages(chatMsgs);
        } else {
          setMessages(prev => mergeById(prev, chatMsgs));
        }
        setTimelineEvents(timeline);
        setDealSummary(summary);
        
        if (opt) {
          setSelectedStrategyId(opt.winningStrategyId);
        }
      } else {
        // Fetch from database backend concurrently
        const [sims, opt, twin, history, chatMsgs, timeline, _cart] = await Promise.all([
          getSimulations(currentMode, customerId),
          getOptimizerResult(currentMode, customerId),
          getDigitalTwinProfile(customerId),
          getTwinHistory(customerId),
          getMessages(customerId),
          getTimelineEvents(customerId),
          loadCart()
        ]);

        setSimulations(sims);
        setOptimizerResult(opt);
        setTwinProfile(twin);
        setTwinHistory(history);
        const sortedMsgs = [...chatMsgs].sort((a, b) => {
          if (!a.created_at || !b.created_at) return 0;
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        });
        if (overwrite) {
          setMessages(sortedMsgs);
        } else {
          setMessages(prev => mergeById(prev, sortedMsgs));
        }
        setTimelineEvents(timeline);

        // --- QUANTITY SYNC: backend is the source of truth ---
        // After every data load, the frontend quantity state is updated from the
        // optimizer result's negotiatedQuantity field, which is derived directly
        // from NegotiationContext.quantity on the backend.
        // This prevents the frontend quantity from ever diverging from what was
        // negotiated and stored in the database.
        // Start from the qtyOverride (explicit caller intent) or the current state value.
        let activeQty: number = qtyOverride ?? quantity;
        if (opt && typeof opt.negotiatedQuantity === 'number' && opt.negotiatedQuantity >= 1) {
          activeQty = opt.negotiatedQuantity;
          // Only call setQuantity when the backend value differs from current state
          // to avoid unnecessary re-renders.
          setQuantity(prev => {
            if (prev !== opt.negotiatedQuantity!) {
              console.info(
                `[DIAG][4→5/6] FRONTEND QUANTITY SYNCED from backend: prev=${prev}, backend=${opt.negotiatedQuantity}`
              );
            }
            return opt.negotiatedQuantity!;
          });
        }

        let stock = 50;
        let minPrice = 0;
        try {
          const fullProd = await apiFetch<any>(`/products/${activeProd.id}`);
          if (fullProd) {
            stock = fullProd.stock_quantity;
            minPrice = fullProd.minimum_price;
          }
        } catch (e: any) {
          console.error("Failed to fetch product details for inventory status", e);
          if (e.message && (e.message.includes("404") || e.message.includes("Not Found"))) {
            console.log("Stale active product detected (404), attempting graceful recovery...");
            try {
              const res = await apiFetch<any[]>('/products/search?q=');
              if (res && res.length > 0) {
                const firstProd = res[0];
                const firstProdId = firstProd.external_product_id || firstProd.id;
                selectProduct(firstProdId);
                return;
              }
            } catch (err) {
              console.error("Failed to recover stale product ID from search list", err);
            }
          }
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

        // Compile DealSummary dynamically in memory from simulations and winner.
        // currentAiOfferPrice is always the UNIT price from the backend.
        // quantity is the negotiated quantity synced from the backend context.
        if (sims.length > 0 && opt) {
          const winningSim = sims.find(s => s.id === opt.winningStrategyId);
          const isInitial = opt.winningStrategyId === 'none' || opt.winningStrategyId === 'initial';

          const discountSim = sims.find(s => s.id === 's_discount');
          const discountPct = (opt && opt.currentDiscountPercent !== undefined)
            ? Math.round(opt.currentDiscountPercent)
            : (isInitial ? 0 : (discountSim ? Math.round(discountSim.discountPercent ?? 0.0) : 15));

          // currentOfferPrice from backend is always the UNIT negotiated price.
          const unitOffer = (opt && opt.currentOfferPrice !== undefined)
            ? opt.currentOfferPrice
            : (isInitial ? activeProd.price : (winningSim ? activeProd.price * (1.0 - (winningSim.discountPercent ?? 0.0) / 100.0) : activeProd.price));
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
            quantity: activeQty,
            bundleItems: isInitial ? [] : (winningSim?.concessions || (winningSim?.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : [])),
            status: chatMsgs.length > 2 ? "Negotiation Active" : "Negotiation Initiated",
            closeProbability: isInitial ? 0.9 : (winningSim?.closeProbability ?? 0.88),
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
            quantity: activeQty,
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
  }, [quantity, customerId, loadCart]);

  // Sync mode changes to components
  useEffect(() => {
    if (!isReplaying) {
      const activeProd = activeProductRef.current;
      if (!activeProd) return;

      const modeChanged = prevModeRef.current !== optimizationMode;
      prevModeRef.current = optimizationMode;

      if (modeChanged) {
        if (!IS_DEMO_MODE && messages.length > 0) {
          // Recalculate simulation values dynamically on the backend when mode changes
          setIsLoading(true);
          const lastUserMsg = [...messages].reverse().find(m => m.sender === 'customer')?.text || `I want a cricket bat`;
          
          runRecalculation(customerId, activeProd.id, quantity, lastUserMsg, optimizationMode)
            .then(({ simulations: newSims, winner: newWinner, digitalTwin: newTwin }) => {
              setSimulations(newSims);
              setOptimizerResult(newWinner);
              if (newWinner) {
                setSelectedStrategyId(newWinner.winningStrategyId);
              }
              
              const isInitial = newWinner?.winningStrategyId === 'none' || newWinner?.winningStrategyId === 'initial';
              const winningSim = !isInitial && newSims.length > 0 ? (newSims.find(s => s.id === newWinner.winningStrategyId) || newSims[0]) : null;
              const discountSim = newSims.length > 0 ? newSims.find(s => s.id === 's_discount') : null;
              const discountPct = (newWinner && newWinner.currentDiscountPercent !== undefined)
                ? Math.round(newWinner.currentDiscountPercent)
                : (isInitial ? 0 : (discountSim ? Math.round(discountSim.discountPercent ?? 0.0) : 15));
              const unitOffer = (newWinner && newWinner.currentOfferPrice !== undefined)
                ? newWinner.currentOfferPrice
                : (isInitial ? activeProd.price : (winningSim ? activeProd.price * (1.0 - (winningSim.discountPercent ?? 0.0) / 100.0) : activeProd.price));

              setDealSummary({
                selectedProductId: activeProd.id,
                currentPrice: activeProd.price,
                customerDiscountRequest: discountPct,
                currentAiOfferPrice: unitOffer,
                bundleItems: isInitial ? [] : (winningSim ? (winningSim.concessions || (winningSim.id === 's_bundle' ? ["Premium English Willow Care Kit", "Dynamic Matrix Scale Grip"] : [])) : []),
                status: "Negotiation Active",
                closeProbability: isInitial ? 0.9 : (winningSim ? winningSim.closeProbability : 0.88),
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
    }
  }, [optimizationMode, loadAllData, isReplaying, messages, customerId, quantity]);

  // Clean timer on unmount
  useEffect(() => {
    return () => {
      if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
    };
  }, []);

  // Product selector reset
  const selectProduct = async (productId: string) => {
    // --- PRODUCT SWITCH RESET ---
    // Synchronously clear all negotiation-specific state before the async product
    // initialization begins. This guarantees that no stale data from the previous
    // product (quantity, discount, offer price, simulations, messages) is ever
    // visible while the new product context is loading.
    setQuantity(1);
    setDealSummary(null);
    setSimulations([]);
    setOptimizerResult(null);
    setMessages([]);
    setTimelineEvents([]);
    setSelectedStrategyId(null);
    setInventoryStatus(null);
    setNearMinimumPrice(false);
    setIsLoading(true);
    
    if (IS_DEMO_MODE) {
      const prod = mockProducts.find(p => p.id === productId) || mockProducts[1];
      setActiveProduct(prod);
      stateManager.resetState(productId);
      await loadAllData(optimizationMode, null, null, true);
    } else {
      try {
        // Initialize negotiation context for the newly selected product.
        // Always start with quantity=1 — the customer has not expressed a quantity
        // for this product yet. The quantity will be updated via extract_quantity
        // as the negotiation conversation progresses.
        const res = await apiFetch<any>('/workspace/select-product', {
          method: 'POST',
          body: JSON.stringify({
            customer_id: customerId,
            product_id: productId,
            quantity: 1
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
            // Build a clean initial DealSummary for the new product.
            // quantity is always 1 here — no negotiation has happened yet.
            setDealSummary({
              ...res.deal_summary,
              quantity: 1,
            });
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
          
          // Full reload with qtyOverride=1 — ensures loadAllData uses the clean
          // starting quantity and does not carry over the previous product's quantity.
          await loadAllData(optimizationMode, resolvedProd, 1, true);
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

    const activeProd = activeProductRef.current;
    if (!activeProd) return;

    setIsTyping(true);
    
    // Add user message to UI immediately for fluid messaging
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const clientMessageId = `temp_u_${Date.now()}`;
    setMessages(prev => [
      ...prev,
      {
        id: clientMessageId,
        sender: 'customer',
        text,
        timestamp: time,
        created_at: new Date().toISOString(),
        role: "user",
        status: "pending",
        client_message_id: clientMessageId
      }
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
      const chatRes = await submitMessage(text, customerId, activeProd.id, quantity, clientMessageId);
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
    const activeProd = activeProductRef.current;
    if (!dealSummary || !activeProd) return;
    try {
      const strategy = selectedStrategyId || 'balanced';
      // currentAiOfferPrice is always the UNIT negotiated price from the backend.
      const negotiated_price = dealSummary.currentAiOfferPrice;
      // quantity is synced from backend NegotiationContext via opt.negotiatedQuantity.
      const negotiated_quantity = dealSummary.quantity;
      const concessions = dealSummary.bundleItems || [];
      const confidence_score = dealSummary.confidenceScore || 0.9;

      console.info(
        `[DIAG][5/6] PROCUREMENT LOCK PAYLOAD: product_id=${activeProd.id}, ` +
        `negotiated_unit_price=${negotiated_price}, quantity=${negotiated_quantity}, ` +
        `total_negotiated_value=${negotiated_price * negotiated_quantity}, ` +
        `catalog_unit_price=${dealSummary.currentPrice}, strategy=${strategy}`
      );

      const response = await apiFetch<any>('/procurement/lock', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: customerId,
          product_id: activeProd.id,
          quantity: negotiated_quantity,
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
  }, [customerId, dealSummary, selectedStrategyId, loadCart]);

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
    
    const activeProd = activeProductRef.current;
    if (IS_DEMO_MODE && activeProd) {
      stateManager.resetState(activeProd.id);
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
  }, []);

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
          } else {
            setActiveProduct(null);
            setIsLoading(false);
          }
        } catch (err) {
          console.error("Failed to load initial product list", err);
          setIsLoading(false);
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
