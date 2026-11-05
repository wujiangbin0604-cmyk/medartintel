import { request } from '@/services/api';
import { browserStorage } from '@/utils/browserStorage';

export type Difficulty = 'beginner' | 'standard' | 'challenge';
export type GameStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'submitting' | 'revealing' | 'finished' | 'error';
export interface ExpertBeat { sample: number; symbol: string; label: string; meaning: string }
export interface ScoreEvent { sample: number; reference_sample: number | null; correct: boolean; delta: number; combo: number }
export interface Result {
  correct: number; incorrect: number; missed: number; precision: number; recall: number;
  score: number; combo_bonus: number; time_bonus: number; max_combo: number;
  events: ScoreEvent[]; answers: ExpertBeat[]; timed_out: boolean; elapsed_seconds: number;
  completed_at: number; grade: string;
}
export interface GameSession {
  session_id: string; difficulty: Difficulty; round: number; status: 'playing' | 'paused' | 'finished' | 'abandoned';
  started_at: number; deadline: number; server_time: number; remaining_seconds: number;
  record_id: string; lead_name: string; sampling_rate: number; start_sample: number; end_sample: number;
  duration: number; signal: number[]; candidate_samples: number[]; samples: number[]; total_score: number;
  speed: number; playback_position: number; result?: Result;
}
export interface GameConfig {
  difficulties: Record<Difficulty, { name: string; seconds: number; duration: number; candidates: boolean; pause: boolean }>;
  scoring: { correct: number; incorrect: number; missed: number; combo_step: number; tolerance_seconds: number };
  rounds: number; level_count: number;
}
export interface History { records: (Omit<Result, 'answers' | 'events'> & { session_id: string; difficulty: Difficulty; round: number })[]; best: Record<Difficulty, number> }
export const names: Record<Difficulty, string> = { beginner: '新手模式', standard: '标准模式', challenge: '挑战模式' };
const base = '/api/games/heartbeat-hunter';
const post = <T,>(path: string, data: unknown, signal?: AbortSignal) => request<T>(base + path, { method: 'POST', body: JSON.stringify(data), signal });
export const gameApi = {
  config: (signal?: AbortSignal) => request<GameConfig>(base + '/config', { signal }),
  history: (id: string, signal?: AbortSignal) => request<History>(base + '/leaderboard?player_id=' + encodeURIComponent(id), { signal }),
  start: (player_id: string, difficulty: Difficulty, previous_session_id?: string, signal?: AbortSignal) => post<GameSession>('/start', { player_id, difficulty, previous_session_id }, signal),
  session: (id: string, signal?: AbortSignal) => request<GameSession>(base + '/session/' + encodeURIComponent(id), { signal }),
  select: (session_id: string, samples: number[], signal?: AbortSignal) => post<{ samples: number[] }>('/selections', { session_id, samples }, signal),
  submit: (session_id: string, samples: number[], signal?: AbortSignal) => post<GameSession>('/submit', { session_id, samples }, signal),
  control: (session_id: string, action: 'pause' | 'resume' | 'abandon' | 'speed', speed = 1, signal?: AbortSignal) => post<Partial<GameSession>>('/control', { session_id, action, speed }, signal),
};
export function playerId() {
  let id = browserStorage.getItem('hunter.player.v1');
  if (!id) {
    // randomUUID needs HTTPS/localhost; deployment by plain server IP must still work.
    if (typeof crypto.randomUUID === 'function') id = crypto.randomUUID();
    else {
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
      id = `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
    }
    browserStorage.setItem('hunter.player.v1', id);
  }
  return id;
}
