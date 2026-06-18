import { IS_DEMO_MODE, apiFetch } from './api';
import { stateManager } from './stateManager';
import { Message, TimelineEvent, DealSummary } from '../types/api';

export async function getMessages(customerId: string): Promise<Message[]> {
  if (IS_DEMO_MODE) {
    return stateManager.getMessages();
  }

  return apiFetch<Message[]>(`/customers/${customerId}/messages`);
}

export async function submitMessage(
  text: string,
  customerId: string,
  productId: string,
  quantity: number
): Promise<any> {
  if (IS_DEMO_MODE) {
    return stateManager.processMessageEvent(text);
  }

  return apiFetch<any>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message: text,
      customer_id: customerId,
      product_id: productId,
      quantity
    })
  });
}

export async function getTimelineEvents(customerId: string): Promise<TimelineEvent[]> {
  if (IS_DEMO_MODE) {
    return stateManager.getTimelineEvents();
  }

  return apiFetch<TimelineEvent[]>(`/customers/${customerId}/timeline`);
}

export async function getDealSummary(
  customerId: string,
  productId: string | null = null,
  quantity: number = 1
): Promise<DealSummary | null> {
  if (IS_DEMO_MODE) {
    return stateManager.getDealSummary();
  }

  // To avoid redundant round-trips, we return null so the state hook can compile it dynamically from simulations & optimizer results in memory.
  return null;
}
