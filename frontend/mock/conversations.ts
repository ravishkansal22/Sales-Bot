import { Message } from '../types/api';

export const mockMessages: Message[] = [
  {
    id: 'm1',
    sender: 'customer',
    text: "Hi team, we're reviewing our vendor spend for the upcoming fiscal year. The current renewal quote of $150,000 for the Enterprise Analytics Platform is significantly above our budget ceiling. We need to see a 30% discount ($105,000) to proceed with renewal.",
    timestamp: "10:15 AM"
  },
  {
    id: 'm2',
    sender: 'company',
    text: "Thanks for reaching out. We highly value our partnership with LogiCore. Given your current usage levels—over 45 million queries processed monthly—a flat 30% reduction is challenging. However, we're committed to finding a mutually beneficial structure.",
    timestamp: "10:17 AM"
  },
  {
    id: 'm3',
    sender: 'customer',
    text: "To be transparent, SaaS-Metrics has pitched us a migration package at $100,000 flat, including a 99.99% uptime SLA. We prefer your platform, but the $50k delta is too wide for our CFO to ignore. We need a competitive proposal by tomorrow.",
    timestamp: "10:19 AM"
  },
  {
    id: 'm4',
    sender: 'company',
    text: "Understood. I will pass this to our pricing optimization committee to run simulation scenarios. We'll address the SLA and financial variance in our proposal shortly.",
    timestamp: "10:21 AM"
  }
];
