import { IS_DEMO_MODE, apiFetch } from './api';
import { stateManager } from './stateManager';
import { mockTwinHistory } from '../mock/digitalTwin';
import { DigitalTwinProfile, TwinHistoryPoint } from '../types/api';

export async function getDigitalTwinProfile(customerId: string): Promise<DigitalTwinProfile> {
  if (IS_DEMO_MODE) {
    return stateManager.getTwinProfile();
  }

  const data = await apiFetch<any>(`/customers/${customerId}/twin`);
  
  // Map snake_case floats [0.0, 1.0] from backend to camelCase integers [0, 100] for frontend
  const priceSensitivity = Math.round((data.price_sensitivity ?? 0.5) * 100);
  const urgency = Math.round((data.urgency ?? 0.5) * 100);
  const riskAversion = Math.round((data.risk_aversion ?? 0.5) * 100);
  const brandLoyalty = Math.round((data.brand_loyalty ?? 0.5) * 100);
  const decisionSpeed = Math.round((data.decision_speed ?? 0.5) * 100);

  // Derive persona name & profile score
  const overallProfileScore = Math.round(((brandLoyalty + (100 - priceSensitivity)) / 2));
  let personaName = 'Balanced B2B Buyer';
  if (priceSensitivity > 75) personaName = 'Price-Sensitive Procurement';
  else if (urgency > 75) personaName = 'High-Urgency Contract Buyer';
  else if (brandLoyalty > 75) personaName = 'Premium Brand Loyalist';

  return {
    priceSensitivity,
    urgency,
    riskAversion,
    brandLoyalty,
    decisionSpeed,
    overallProfileScore,
    personaName,
    description: `Calibrated digital twin profile based on real customer transaction spend, return patterns, and category purchase affinity.`
  };
}

export async function getTwinHistory(customerId: string): Promise<TwinHistoryPoint[]> {
  if (IS_DEMO_MODE) {
    const current = stateManager.getTwinProfile();
    return [
      ...mockTwinHistory.slice(0, 3),
      {
        timestamp: "Current State (Active)",
        priceSensitivity: current.priceSensitivity,
        urgency: current.urgency,
        riskAversion: current.riskAversion,
        brandLoyalty: current.brandLoyalty,
        decisionSpeed: current.decisionSpeed
      }
    ];
  }

  const history = await apiFetch<any[]>(`/customers/${customerId}/twin-history`);
  
  return history.map(snap => ({
    timestamp: snap.timestamp || "Snapshot",
    priceSensitivity: snap.priceSensitivity ?? Math.round((snap.price_sensitivity ?? 0.5) * 100),
    urgency: snap.urgency ?? Math.round((snap.urgency ?? 0.5) * 100),
    riskAversion: snap.riskAversion ?? Math.round((snap.risk_aversion ?? 0.5) * 100),
    brandLoyalty: snap.brandLoyalty ?? Math.round((snap.brand_loyalty ?? 0.5) * 100),
    decisionSpeed: snap.decisionSpeed ?? Math.round((snap.decision_speed ?? 0.5) * 100),
  }));
}
