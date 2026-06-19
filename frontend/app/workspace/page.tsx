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
  const [catalogWidth, setCatalogWidth] = React.useState(22); // default 22%
  const [dealWidth, setDealWidth] = React.useState(30);       // default 30%

  const startResizeCatalog = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = catalogWidth;
    
    const doDrag = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const container = document.getElementById('workspace-container');
      const containerWidth = container ? container.clientWidth : 1200;
      const deltaPct = (deltaX / containerWidth) * 100;
      let newWidth = startWidth + deltaPct;
      if (newWidth < 15) newWidth = 15;
      if (newWidth > 35) newWidth = 35;
      setCatalogWidth(newWidth);
    };
    
    const stopDrag = () => {
      document.removeEventListener('mousemove', doDrag);
      document.removeEventListener('mouseup', stopDrag);
    };
    
    document.addEventListener('mousemove', doDrag);
    document.addEventListener('mouseup', stopDrag);
  };

  const startResizeDeal = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = dealWidth;
    
    const doDrag = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const container = document.getElementById('workspace-container');
      const containerWidth = container ? container.clientWidth : 1200;
      const deltaPct = (deltaX / containerWidth) * 100;
      let newWidth = startWidth - deltaPct; // pull from left boundary
      if (newWidth < 20) newWidth = 20;
      if (newWidth > 40) newWidth = 40;
      setDealWidth(newWidth);
    };
    
    const stopDrag = () => {
      document.removeEventListener('mousemove', doDrag);
      document.removeEventListener('mouseup', stopDrag);
    };
    
    document.addEventListener('mousemove', doDrag);
    document.addEventListener('mouseup', stopDrag);
  };

  return (
    <div className="relative h-screen bg-deep-black text-slate-100 flex flex-col z-0 overflow-hidden">
      
      {/* Animated canvas grid particle network */}
      <GridBackground />
      
      {/* Navigation Bar */}
      <Navbar />
 
      {/* Global Informative Alert Bar */}
      <div className="w-full bg-cyan-glow/5 border-b border-cyan-glow/15 px-6 py-2 shrink-0">
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
      <main 
        id="workspace-container"
        className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex flex-col lg:flex-row gap-4 overflow-hidden min-h-0"
      >
        
        {/* Column 1: Generic Product Catalog */}
        <div 
          className="w-full lg:flex flex-col h-full min-h-0 shrink-0"
          style={{ width: `${catalogWidth}%` }}
        >
          <Catalog />
        </div>

        {/* Divider 1 */}
        <div 
          onMouseDown={startResizeCatalog}
          className="hidden lg:block w-1.5 hover:w-2 bg-white/5 hover:bg-cyan-glow/20 cursor-col-resize self-stretch transition-all rounded shrink-0"
          title="Drag to resize panels"
        />
 
        {/* Column 2: Negotiation Chat */}
        <div className="flex-1 flex flex-col h-full min-h-0">
          <ChatInterface />
        </div>

        {/* Divider 2 */}
        <div 
          onMouseDown={startResizeDeal}
          className="hidden lg:block w-1.5 hover:w-2 bg-white/5 hover:bg-cyan-glow/20 cursor-col-resize self-stretch transition-all rounded shrink-0"
          title="Drag to resize panels"
        />
 
        {/* Column 3: Current Deal Summary & Confidence Ring */}
        <div 
          className="w-full lg:flex flex-col h-full min-h-0 shrink-0"
          style={{ width: `${dealWidth}%` }}
        >
          <DealSummaryPanel />
        </div>
 
      </main>
      
    </div>
  );
}
