import { browserStorage } from '@/utils/browserStorage';

export const WELCOME_KEY = 'ecg_ai_welcome_v1';
export const TUTORIAL_KEY = 'ecg_ai_hunter_tutorial_v1';
export const WELCOME_EVENT = 'ecg-ai:show-welcome';
export const GAME_PATH = '/interactive-lab/heartbeat-hunter';
export function hasCompletedWelcome() {
  try { const value = JSON.parse(browserStorage.getItem(WELCOME_KEY) || 'null'); return value?.version === 1 && value.completed === true; }
  catch { return false; }
}
export function completeWelcome(choice: 'challenge' | 'browse' | 'close', doNotAutoShow: boolean) {
  browserStorage.setItem(WELCOME_KEY, JSON.stringify({ version: 1, completed: true, choice, doNotAutoShow, completedAt: new Date().toISOString() }));
}
export function showWelcome() { window.dispatchEvent(new Event(WELCOME_EVENT)); }

export function gameAnalysisUrl(record: string, sample: number, samplingRate: number, ai = true) {
  const query = new URLSearchParams({ record_id: record, annotation_sample: String(sample), task: 'nv', time: String(sample / samplingRate), from: 'heartbeat-hunter' });
  return `${ai ? '/ai-inference' : '/ai-detection'}?${query}`;
}
