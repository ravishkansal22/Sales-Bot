'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { Send, Cpu, User, Sparkles, AlertCircle, ShoppingBag, Gift } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ChatInterface() {
  const { 
    messages, 
    sendUserMessage, 
    isTyping, 
    typingStatus, 
    activeProduct,
    dealSummary 
  } = useNegotiationState();

  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    sendUserMessage(input);
    setInput('');
  };

  const handlePromptClick = (text: string) => {
    if (isTyping) return;
    sendUserMessage(text);
  };

  const getSpecialOffer = (text: string) => {
    const lowerText = text.toLowerCase();
    
    // Parse if it represents an offer response
    if (lowerText.includes('offer') || lowerText.includes('bundle') || lowerText.includes('concession')) {
      if (dealSummary) {
        return {
          productName: activeProduct.name,
          price: dealSummary.currentAiOfferPrice,
          discount: dealSummary.customerDiscountRequest || 10,
          bundles: dealSummary.bundleItems,
          valid: 'Offer Secured — Awaiting Acceptance'
        };
      }
    }
    return null;
  };

  const promptSuggestions = [
    { text: "Mention competitor offer is 20% cheaper.", label: "Competitor Leverage" },
    { text: "Request a 15% discount for a bulk trial contract.", label: "Discount Target" },
    { text: "What accessories can you bundle with the bat?", label: "Ask for Bundles" },
    { text: "I accept the calibrated proposal terms.", label: "Accept Deal" }
  ];

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-[550px]">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div className="flex items-center space-x-2">
          <Cpu className="h-4 w-4 text-cyan-glow" />
          <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
            AI Sales Negotiation Assistant
          </span>
        </div>
        <div className="flex items-center space-x-1.5 font-mono text-[9px] text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>NEGOTIATION STREAM: SECURE</span>
        </div>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin mb-4">
        <AnimatePresence initial={false}>
          {messages.map((msg) => {
            const isCustomer = msg.sender === 'customer';
            const offer = !isCustomer ? getSpecialOffer(msg.text) : null;

            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex flex-col max-w-[85%] ${isCustomer ? 'ml-auto items-end' : 'mr-auto items-start'}`}
              >
                {/* Chat Bubble */}
                <div className={`rounded-xl p-4 border text-xs leading-relaxed font-sans ${
                  isCustomer
                    ? 'bg-cyan-glow/5 border-cyan-glow/20 text-white shadow-[0,0,10px_rgba(0,242,254,0.02)]'
                    : 'bg-white/[0.02] border-white/10 text-white/90'
                }`}>
                  <div className="flex items-center justify-between space-x-8 mb-1.5 border-b border-white/5 pb-1 font-mono text-[9px] text-white/40">
                    <span className="font-bold uppercase tracking-wider flex items-center space-x-1">
                      {isCustomer ? (
                        <>
                          <User className="h-3 w-3 text-cyan-glow" />
                          <span>Buyer (Procurement)</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3 w-3 text-neon-purple animate-pulse" />
                          <span>Ghost Negotiator Engine</span>
                        </>
                      )}
                    </span>
                    <span>{msg.timestamp}</span>
                  </div>
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                </div>

                {/* Inline Special Offer Card */}
                {offer && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.96, y: 5 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-3 w-full rounded-xl border border-cyan-glow/40 bg-gradient-to-br from-cyan-glow/[0.04] to-indigo-500/[0.04] p-4.5 shadow-[0_0_20px_rgba(0,242,254,0.08)] backdrop-blur-md"
                  >
                    <div className="flex justify-between items-center border-b border-cyan-glow/20 pb-2.5 mb-3">
                      <div className="flex items-center space-x-2">
                        <ShoppingBag className="h-4 w-4 text-cyan-glow" />
                        <span className="font-mono text-[10px] font-bold text-white uppercase tracking-wider">
                          Calibrated Proposal Offer
                        </span>
                      </div>
                      <span className="rounded bg-cyan-glow/10 border border-cyan-glow/20 px-2 py-0.5 font-mono text-[8px] text-cyan-glow uppercase tracking-wider font-bold">
                        AI Optimized
                      </span>
                    </div>

                    <div className="space-y-2.5 text-xs font-sans">
                      <div className="flex justify-between">
                        <span className="text-white/50">Item Spec:</span>
                        <span className="text-white font-bold">{offer.productName}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/50">Calibrated Price:</span>
                        <span className="text-cyan-glow font-mono font-bold text-sm">
                          ₹{offer.price.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/50">Applied Concession:</span>
                        <span className="text-amber-400 font-mono font-bold">
                          {offer.discount}% Discount
                        </span>
                      </div>

                      {offer.bundles.length > 0 && (
                        <div className="border-t border-white/5 pt-2 mt-1 space-y-1.5">
                          <span className="font-mono text-[8px] text-white/40 block uppercase tracking-wider">
                            Bundled Agreements
                          </span>
                          {offer.bundles.map((item, idx) => (
                            <div key={idx} className="flex items-center space-x-1.5 text-[10.5px] text-emerald-400">
                              <Gift className="h-3 w-3 shrink-0" />
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="border-t border-white/5 pt-2.5 mt-3 text-center">
                      <span className="font-mono text-[9px] text-white/30 uppercase tracking-widest leading-none block">
                        {offer.valid}
                      </span>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Typing and backend status indicators */}
        {isTyping && (
          <motion.div 
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center space-x-3 p-3 rounded-xl border border-white/5 bg-white/[0.01] max-w-[85%] mr-auto"
          >
            <div className="flex items-center space-x-1">
              <span className="h-1.5 w-1.5 bg-cyan-glow rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
              <span className="h-1.5 w-1.5 bg-cyan-glow rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
              <span className="h-1.5 w-1.5 bg-cyan-glow rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
            </div>
            <span className="font-mono text-[9px] text-white/40 uppercase tracking-wider animate-pulse">
              {typingStatus}
            </span>
          </motion.div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Suggested prompts buttons */}
      <div className="mb-4">
        <p className="text-[8px] font-mono text-white/30 tracking-widest uppercase mb-2">
          Suggested Actions
        </p>
        <div className="flex flex-wrap gap-1.5">
          {promptSuggestions.map((prompt, i) => (
            <button
              key={i}
              disabled={isTyping}
              onClick={() => handlePromptClick(prompt.text)}
              className="rounded bg-white/5 border border-white/10 px-2.5 py-1 font-mono text-[9px] text-white/70 hover:text-cyan-glow hover:border-cyan-glow/45 hover:bg-cyan-glow/5 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {prompt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Message Input Panel */}
      <form onSubmit={handleSubmit} className="flex space-x-3 items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isTyping ? "AI is processing simulations..." : "Discuss pricing concessions or bundle terms..."}
          disabled={isTyping}
          className="flex-1 bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-xs text-white placeholder-white/30 focus:outline-none focus:border-cyan-glow/50 focus:shadow-[0_0_10px_rgba(0,242,254,0.05)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={isTyping || !input.trim()}
          className="h-9 w-9 rounded-lg border border-cyan-glow/30 bg-cyan-glow/10 flex items-center justify-center text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.08)] hover:shadow-[0_0_15px_rgba(0,242,254,0.3)] hover:bg-cyan-glow/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>

    </div>
  );
}
