// By default, demo mode is disabled (integrated FastAPI backend mode). Set NEXT_PUBLIC_DEMO_MODE=true in your environment to run in local mock mode.
export const IS_DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

export const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BACKEND_URL}${path}`;
  const maxRetries = 3;
  let attempt = 0;

  while (attempt < maxRetries) {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        // If it's a 404 Not Found error, throw immediately as retrying won't help
        if (response.status === 404) {
          throw new Error(`API Error: Not Found (${response.status})`);
        }
        throw new Error(`API Error: ${response.statusText} (${response.status})`);
      }

      return await response.json() as T;
    } catch (error: any) {
      attempt++;
      // If it is a 404 error we threw above, propagate it immediately
      if (error.message && error.message.includes('404')) {
        throw error;
      }
      console.warn(`apiFetch attempt ${attempt} failed for ${path}:`, error.message || error);
      if (attempt >= maxRetries) {
        throw error;
      }
      // Exponential backoff delay: 500ms, 1000ms...
      await new Promise(resolve => setTimeout(resolve, 500 * attempt));
    }
  }
  throw new Error("API Fetch failed after retries");
}
