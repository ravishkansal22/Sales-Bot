'use client';

import React from 'react';
import { NegotiationProvider } from '../../hooks/useNegotiationState';
import Navbar from '../../components/Navbar';
import GridBackground from '../../components/GridBackground';
import Catalog from '../../features/workspace/Catalog';
import ChatInterface from '../../features/workspace/ChatInterface';
import DealSummaryPanel from '../../features/workspace/DealSummaryPanel';
import { Sparkles, Eye, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export default function WorkspacePage() {
  return (
    <div className="relative min-h-screen bg-deep-black text-slate-100 flex flex-col z-0">
      
      {/* Animated canvas grid particle network */}
      <GridBackground />
      
      {/* Navigation Bar */}
      <Navbar />

      {/* Global Informative Alert Bar */}
      <div className="w-full bg-cyan-glow/5 border-b border-cyan-glow/15 px-6 py-2.5 text-center">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-2 font-mono text-[10px] text-cyan-glow tracking-wider">
          <Sparkles className="h-4 w-4 animate-spin text-cyan-glow shrink-0" />
          <span>YOU ARE OPERATING THE AI WORKSPACE. EACH NEGOTIATION PATHWAY INITIATES 24 DYNAMIC SIMULATIONS.</span>
          <Link 
            href="/dashboard"
            className="inline-flex items-center space-x-1 underline hover:text-white font-bold shrink-0 ml-1.5"
          >
            <span>INSPECT SIMULATION ENGINE</span>
            <Eye className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* Workspace Columns Container */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex flex-col lg:flex-row gap-6 overflow-hidden">
        
        {/* Column 1: Generic Product Catalog (25% width on desktop) */}
        <div className="w-full lg:w-1/4 shrink-0 flex flex-col">
          <Catalog />
        </div>

        {/* Column 2: Negotiation Chat (50% width on desktop) */}
        <div className="flex-1 flex flex-col">
          <ChatInterface />
        </div>

        {/* Column 3: Current Deal Summary & Confidence Ring (25% width on desktop) */}
        <div className="w-full lg:w-1/4 shrink-0 flex flex-col">
          <DealSummaryPanel />
        </div>

      </main>
      
    </div>
  );
}
