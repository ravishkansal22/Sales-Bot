// By default, demo mode is disabled (integrated FastAPI backend mode). Set NEXT_PUBLIC_DEMO_MODE=true in your environment to run in local mock mode.
export const IS_DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

export const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BACKEND_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText} (${response.status})`);
  }

  return response.json() as Promise<T>;
}
