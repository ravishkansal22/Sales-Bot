'use client';

import React, { useState } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { FileText, CheckCircle, Trash2, Plus, Minus, Lock, ShoppingCart, RefreshCw, AlertTriangle, ShieldAlert, Info } from 'lucide-react';
import { motion } from 'framer-motion';

export default function DealSummaryPanel() {
  const { 
    dealSummary, 
    activeProduct,
    cart,
    inventoryStatus,
    nearMinimumPrice,
    lockCurrentDeal,
    removeFromCart,
    updateCartQuantity,
    reopenNegotiation,
    finalizePurchase,
    quantity
  } = useNegotiationState();

  const [activeTab, setActiveTab] = useState<'summary' | 'cart'>('summary');

  if (!dealSummary || !activeProduct) {
    return (
      <div className="glass-panel rounded-xl p-5 flex flex-col justify-center items-center h-full min-h-[300px]">
        <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
        <span className="font-mono text-xs text-white/30 tracking-widest uppercase">
          {!activeProduct ? "Please Select a Product..." : "Compiling Deal Summary..."}
        </span>
      </div>
    );
  }

  // Radial Progress Ring values for Confidence Score
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const confidencePct = Math.round(dealSummary.confidenceScore * 100);
  const strokeDashoffset = circumference - (confidencePct / 100) * circumference;

  // [DIAG][6/6] Cart & summary render diagnostic — confirms which quantity and unit price
  // are being displayed and will be sent on procurement lock.
  const summaryQty = dealSummary.quantity ?? 1;
  const summaryUnitPrice = dealSummary.currentAiOfferPrice;
  const summaryTotalValue = summaryUnitPrice * summaryQty;
  console.info(
    `[DIAG][6/6] DEAL SUMMARY RENDER: product=${activeProduct.name}, ` +
    `catalog_unit_price=${dealSummary.currentPrice}, ` +
    `negotiated_unit_price=${summaryUnitPrice}, ` +
    `quantity=${summaryQty}, ` +
    `total_negotiated_value=${summaryTotalValue}`
  );

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes('ratified') || s.includes('concluded') || s.includes('final')) return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5';
    if (s.includes('threat') || s.includes('objection') || s.includes('active')) return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
    return 'text-cyan-glow border-cyan-glow/20 bg-cyan-glow/5';
  };

  const handleLock = async () => {
    await lockCurrentDeal();
    setActiveTab('cart');
  };

  const handleReopen = async (dealId: string) => {
    await reopenNegotiation(dealId);
    setActiveTab('summary');
  };

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-0">
      
      {/* Tabs Header */}
      <div className="flex border-b border-white/10 mb-4 shrink-0">
        <button
          onClick={() => setActiveTab('summary')}
          className={`flex-1 py-2.5 font-mono text-[9px] uppercase tracking-wider font-bold text-center border-b-2 transition-all ${
            activeTab === 'summary' 
              ? 'border-cyan-glow text-white shadow-[0_4px_10px_-4px_rgba(0,242,254,0.3)]' 
              : 'border-transparent text-white/40 hover:text-white/70'
          }`}
        >
          Deal Summary
        </button>
        <button
          onClick={() => setActiveTab('cart')}
          className={`flex-1 py-2.5 font-mono text-[9px] uppercase tracking-wider font-bold text-center border-b-2 transition-all relative ${
            activeTab === 'cart' 
              ? 'border-cyan-glow text-white shadow-[0_4px_10px_-4px_rgba(0,242,254,0.3)]' 
              : 'border-transparent text-white/40 hover:text-white/70'
          }`}
        >
          Procurement Cart
          {cart?.items?.length > 0 && (
            <span className="absolute top-1 right-2 bg-cyan-glow text-black font-sans text-[8px] font-extrabold h-4 w-4 rounded-full flex items-center justify-center">
              {cart.items.length}
            </span>
          )}
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 flex flex-col justify-between overflow-hidden">
        {activeTab === 'summary' ? (
          <div className="flex-1 flex flex-col justify-between overflow-y-auto">
            <div className="space-y-4">
              
              {/* Active Product Name */}
              <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg">
                <span className="font-mono text-[9px] text-white/30 uppercase block tracking-wider">
                  Selected Agreement Item
                </span>
                <span className="font-sans text-xs font-bold text-white mt-1 block uppercase">
                  {activeProduct.name}
                </span>
                <div className="flex justify-between mt-2 font-mono text-[10px] border-t border-white/5 pt-2">
                  <span className="text-white/40">CATALOG VALUE:</span>
                  <span className="text-white/80">₹{activeProduct.price.toLocaleString()}</span>
                </div>
              </div>

              {/* Pricing Concessions */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
                  <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                    APPROVED DISCOUNT
                  </span>
                  <span className="font-mono text-sm font-bold text-amber-400 block mt-1.5 leading-none">
                    {dealSummary.customerDiscountRequest}%
                  </span>
                </div>
                
                <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
                  <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                    Calibrated Unit Price
                  </span>
                  <span className="font-mono text-sm font-bold text-cyan-glow block mt-1.5 leading-none">
                    ₹{summaryUnitPrice.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Quantity & Total Negotiated Value */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
                  <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                    Negotiated Qty
                  </span>
                  <span className="font-mono text-sm font-bold text-white block mt-1.5 leading-none">
                    {summaryQty.toLocaleString()}
                  </span>
                </div>
                
                <div className="p-3 bg-black/40 border border-white/5 rounded-lg text-left">
                  <span className="font-mono text-[8.5px] text-white/40 uppercase block leading-none">
                    Total Value
                  </span>
                  <span className="font-mono text-sm font-bold text-emerald-400 block mt-1.5 leading-none">
                    ₹{summaryTotalValue.toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Bundle items list */}
              {dealSummary.bundleItems.length > 0 ? (
                <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg space-y-1.5">
                  <span className="font-mono text-[9px] text-white/30 uppercase block tracking-wider border-b border-white/5 pb-1">
                    Concession Package
                  </span>
                  {dealSummary.bundleItems.map((item, idx) => (
                    <div key={idx} className="flex items-center space-x-1.5 text-[10px] text-emerald-400 font-sans">
                      <CheckCircle className="h-3 w-3 shrink-0" />
                      <span className="truncate">{item}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 bg-white/[0.01] border border-white/5 rounded-lg text-center">
                  <span className="font-mono text-[9px] text-white/30 uppercase tracking-widest leading-none block py-1">
                    No Bundles Added
                  </span>
                </div>
              )}

              {/* Close Probability */}
              <div className="space-y-1.5">
                <div className="flex justify-between font-mono text-[9px] text-white/40 leading-none">
                  <span>ESTIMATED CLOSE PROBABILITY</span>
                  <span className="font-bold text-white">{(dealSummary.closeProbability * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${dealSummary.closeProbability * 100}%` }}
                    className="h-full bg-cyan-glow shadow-[0_0_8px_rgba(0,242,254,0.4)]"
                  />
                </div>
              </div>

              {/* Status badge */}
              <div className="flex items-center justify-between border-t border-white/5 pt-3">
                <span className="font-mono text-[9px] text-white/40 uppercase leading-none">
                  Deal Status
                </span>
                <span className={`rounded-md border px-2 py-0.5 font-mono text-[9px] font-bold uppercase ${getStatusColor(dealSummary.status)}`}>
                  {dealSummary.status}
                </span>
              </div>

              {/* Inventory alerts & price floor exposure */}
              <div className="space-y-1.5 pt-2 border-t border-white/5">
                {inventoryStatus && (
                  <div className={`flex items-center space-x-2 border rounded-md px-3 py-2 text-[10.5px] font-sans ${
                    inventoryStatus === "Low Inventory"
                      ? "text-red-400 border-red-500/20 bg-red-500/5 animate-pulse"
                      : inventoryStatus === "High Inventory"
                      ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/5"
                      : "text-amber-400 border-amber-500/20 bg-amber-500/5"
                  }`}>
                    {inventoryStatus === "Low Inventory" ? (
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-red-400" />
                    ) : (
                      <Info className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>Inventory state: <strong>{inventoryStatus}</strong></span>
                  </div>
                )}

                {nearMinimumPrice && (
                  <div className="flex items-center space-x-2 border border-purple-500/20 bg-purple-500/5 text-purple-400 rounded-md px-3 py-2 text-[10.5px] font-sans animate-pulse">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-purple-400" />
                    <span>Price limits: <strong>Near Minimum Price Limit</strong></span>
                  </div>
                )}
              </div>

            </div>

            {/* Bottom Actions & Simulation Telemetry */}
            <div className="space-y-3 mt-4 shrink-0">
              <button
                onClick={handleLock}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-mono font-bold text-xs uppercase tracking-wider flex items-center justify-center space-x-2 transition-all shadow-[0_0_15px_rgba(0,242,254,0.15)] hover:shadow-[0_0_20px_rgba(0,242,254,0.35)]"
              >
                <Lock className="h-3.5 w-3.5" />
                <span>Lock & Add to Cart</span>
              </button>

              <div className="border-t border-white/10 pt-3 flex items-center justify-between bg-white/[0.005]">
                <div className="flex flex-col text-left">
                  <span className="font-mono text-[9px] text-white/30 uppercase leading-none block">
                    Simulation Telemetry
                  </span>
                  <span className="font-mono text-[10px] font-bold text-white mt-1 block uppercase tracking-wider">
                    Negotiation Confidence
                  </span>
                  <span className="font-mono text-[8px] text-white/40 leading-none mt-1">
                    Objective: {dealSummary.optimizationObjective}
                  </span>
                </div>

                <div className="relative flex h-12 w-12 items-center justify-center shrink-0">
                  {/* SVG circle */}
                  <svg className="absolute inset-0 w-full h-full -rotate-90">
                    <circle
                      cx="24"
                      cy="24"
                      r={radius}
                      className="text-white/5"
                      strokeWidth="3.5"
                      stroke="currentColor"
                      fill="none"
                    />
                    <motion.circle
                      cx="24"
                      cy="24"
                      r={radius}
                      className="text-cyan-glow"
                      strokeWidth="3.5"
                      stroke="currentColor"
                      fill="none"
                      strokeDasharray={circumference}
                      initial={{ strokeDashoffset: circumference }}
                      animate={{ strokeDashoffset }}
                      transition={{ duration: 0.8 }}
                      style={{
                        filter: 'drop-shadow(0px 0px 4px rgba(0, 242, 254, 0.4))'
                      }}
                    />
                  </svg>
                  <span className="font-mono text-[10px] font-bold text-white z-10">
                    {confidencePct}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Cart Tab Content */
          <div className="flex-1 flex flex-col justify-between overflow-hidden">
            {cart && cart.items && cart.items.length > 0 ? (
              <div className="flex flex-col h-full justify-between">
                {/* Cart List */}
                <div className="space-y-3 overflow-y-auto max-h-[340px] pr-1 scrollbar-thin">
                  {cart.items.map((item: any) => (
                    <div key={item.deal_id} className="p-3 bg-white/[0.02] border border-white/5 rounded-lg flex flex-col justify-between">
                      <div>
                        <div className="flex justify-between items-start">
                          <span className="font-sans font-bold text-white text-xs block uppercase max-w-[70%] truncate">
                            {item.product_name}
                          </span>
                          <button
                            onClick={() => removeFromCart(item.deal_id)}
                            className="text-white/30 hover:text-red-400 transition-all p-0.5"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        <div className="flex justify-between mt-1 text-[10.5px] font-mono">
                          <span className="text-white/40">UNIT PRICE:</span>
                          <span className="text-cyan-glow font-bold">₹{item.negotiated_price.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between mt-0.5 text-[10.5px] font-mono">
                          <span className="text-white/40">QTY × UNIT:</span>
                          <span className="text-white/70">{item.quantity} × ₹{item.negotiated_price.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between mt-0.5 text-[10.5px] font-mono">
                          <span className="text-white/40">LINE TOTAL:</span>
                          <span className="text-emerald-400 font-bold">₹{(item.negotiated_price * item.quantity).toLocaleString()}</span>
                        </div>
                        
                        {item.concessions && item.concessions.length > 0 && (
                          <div className="mt-1.5 space-y-1">
                            {item.concessions.map((con: string, idx: number) => (
                              <div key={idx} className="flex items-center space-x-1 text-[9.5px] text-emerald-400 font-sans">
                                <CheckCircle className="h-2.5 w-2.5 shrink-0" />
                                <span className="truncate">{con}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center justify-between border-t border-white/5 pt-2 mt-2.5 font-mono">
                        {/* Quantity Selector */}
                        <div className="flex items-center space-x-1.5 bg-black/40 border border-white/10 rounded px-1.5 py-0.5">
                          <button
                            onClick={() => updateCartQuantity(item.deal_id, Math.max(1, item.quantity - 1))}
                            className="text-white/50 hover:text-white transition-all"
                          >
                            <Minus className="h-3 w-3" />
                          </button>
                          <span className="text-white text-[10.5px] font-bold min-w-[15px] text-center">
                            {item.quantity}
                          </span>
                          <button
                            onClick={() => updateCartQuantity(item.deal_id, item.quantity + 1)}
                            className="text-white/50 hover:text-white transition-all"
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                        </div>

                        {/* Reopen Negotiation */}
                        <button
                          onClick={() => handleReopen(item.deal_id)}
                          className="flex items-center space-x-1 text-[9px] text-amber-400 hover:text-amber-300 font-bold uppercase transition-all bg-amber-400/5 hover:bg-amber-400/10 border border-amber-400/20 px-2 py-1 rounded"
                        >
                          <RefreshCw className="h-2.5 w-2.5 animate-spin-hover" />
                          <span>Reopen</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Cart Summary & Purchase button */}
                <div className="border-t border-white/10 pt-3 mt-4 space-y-3 shrink-0">
                  <div className="p-3 bg-black/40 border border-white/5 rounded-lg space-y-1.5 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-white/40">TOTAL ITEMS:</span>
                      <span className="text-white font-bold">{cart.summary.total_items}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/40">CATALOG VALUE:</span>
                      <span className="text-white/80">₹{cart.summary.catalog_total.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-t border-white/5 pt-1.5">
                      <span className="text-white/40">CONTRACT TOTAL:</span>
                      <span className="text-cyan-glow font-bold">₹{cart.summary.negotiated_total.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-t border-white/5 pt-1.5 text-emerald-400 font-bold">
                      <span>SAVINGS ({cart.summary.average_savings_pct.toFixed(1)}%):</span>
                      <span className="shadow-[0_0_10px_rgba(16,185,129,0.15)]">₹{cart.summary.total_savings.toLocaleString()}</span>
                    </div>
                  </div>

                  <button
                    onClick={finalizePurchase}
                    className="w-full py-2.5 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-black font-mono font-bold text-xs uppercase tracking-wider flex items-center justify-center space-x-2 transition-all shadow-[0_0_15px_rgba(16,185,129,0.15)] hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                  >
                    <ShoppingCart className="h-3.5 w-3.5" />
                    <span>Finalize Purchase</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col justify-center items-center text-center p-5 border border-dashed border-white/10 rounded-lg">
                <ShoppingCart className="h-8 w-8 text-white/10 mb-3" />
                <span className="font-mono text-[10px] text-white/30 uppercase tracking-wider block mb-1">
                  Cart is Empty
                </span>
                <p className="text-[10px] text-white/40 max-w-[200px] leading-relaxed">
                  Calibrate agreement terms and select "Lock & Add to Cart" to compile B2B bulk orders.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
