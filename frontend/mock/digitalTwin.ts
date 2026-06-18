import { DigitalTwinProfile, TwinHistoryPoint } from '../types/api';

export const mockTwinProfile: DigitalTwinProfile = {
  priceSensitivity: 85,
  urgency: 90,
  riskAversion: 65,
  brandLoyalty: 40,
  decisionSpeed: 75,
  overallProfileScore: 78,
  personaName: "High-Urgency Price-Sensitive Migrator",
  description: "LogiCore's team is under pressure to cut vendor costs but is facing tight operational renewal deadlines. They prefer our feature set but are actively using a competitor's aggressive offer as leverage."
};

export const mockTwinHistory: TwinHistoryPoint[] = [
  {
    timestamp: "Kickoff (T-30d)",
    priceSensitivity: 45,
    urgency: 30,
    riskAversion: 50,
    brandLoyalty: 80,
    decisionSpeed: 40
  },
  {
    timestamp: "Proposal Sent (T-15d)",
    priceSensitivity: 55,
    urgency: 50,
    riskAversion: 55,
    brandLoyalty: 75,
    decisionSpeed: 50
  },
  {
    timestamp: "Objection Filed (T-5d)",
    priceSensitivity: 75,
    urgency: 75,
    riskAversion: 60,
    brandLoyalty: 60,
    decisionSpeed: 65
  },
  {
    timestamp: "Current State (Active)",
    priceSensitivity: 85,
    urgency: 90,
    riskAversion: 65,
    brandLoyalty: 40,
    decisionSpeed: 75
  }
];
