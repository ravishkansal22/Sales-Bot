'use client';

import React from 'react';
import { NegotiationProvider } from '../../hooks/useNegotiationState';
import Navbar from '../../components/Navbar';
import GridBackground from '../../components/GridBackground';
import LeftPanel from '../../features/dashboard/LeftPanel';
import SimulationGraph from '../../features/dashboard/SimulationGraph';
import SimulationEngine from '../../features/dashboard/SimulationEngine';
import DecisionCenter from '../../features/dashboard/DecisionCenter';
import DigitalTwin from '../../features/dashboard/DigitalTwin';
import Financials from '../../features/dashboard/Financials';
import ComparisonTable from '../../features/dashboard/ComparisonTable';
import TwinEvolution from '../../features/dashboard/TwinEvolution';

export default function DashboardPage() {
  return (
    <div className="relative min-h-screen bg-deep-black text-slate-100 flex flex-col z-0">
      
      {/* Animated canvas grid particle network */}
      <GridBackground />
      
      {/* Navigation Bar */}
      <Navbar />

      {/* Dashboard Workspace */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex flex-col lg:flex-row gap-6 overflow-hidden">
        
        {/* Left Panel: Customer feed & timeline (25% width on desktop) */}
        <div className="w-full lg:w-1/4 shrink-0 flex flex-col">
          <LeftPanel />
        </div>

        {/* Right Panel: Strategy control cockpit (75% width on desktop) */}
        <div className="flex-1 flex flex-col space-y-6">
          
          {/* Row 1: Graph (60%) & Simulation Options (40%) */}
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
            <div className="xl:col-span-3">
              <SimulationGraph />
            </div>
            <div className="xl:col-span-2">
              <SimulationEngine />
            </div>
          </div>

          {/* Row 2: Optimization Recommended Hero & Active mode selectors */}
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
            <div className="xl:col-span-3">
              <DecisionCenter />
            </div>
            <div className="xl:col-span-2">
              <DigitalTwin />
            </div>
          </div>

          {/* Row 3: Financials KPI metrics cards */}
          <Financials />

          {/* Row 4: Bloomberg Grid (60%) & Twin history chart (40%) */}
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
            <div className="xl:col-span-3">
              <ComparisonTable />
            </div>
            <div className="xl:col-span-2">
              <TwinEvolution />
            </div>
          </div>

        </div>

      </main>
      
    </div>
  );
}
