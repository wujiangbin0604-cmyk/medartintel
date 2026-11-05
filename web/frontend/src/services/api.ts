import type {
  BeatAnnotation, BeatDetail, ModelId, ModelStatus, PlaybackSegment,
  Prediction, RecordSummary, TaskName, WaveWindow,
} from '@/types/ecg';

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const forwardAbort = () => controller.abort();
  init?.signal?.addEventListener('abort', forwardAbort, { once: true });
  if (init?.signal?.aborted) controller.abort();
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, 30000);
  try {
  const response = await fetch(url, {
    ...init,
    signal: controller.signal,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : Array.isArray(payload?.detail) ? payload.detail.map((row: { msg: string }) => row.msg).join('；') : `请求失败 (HTTP ${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
  } catch (error) {
    if (timedOut) throw new Error('请求超时（30 秒），请检查本地后端服务后重试');
    if ((error as Error).name === 'TypeError') throw new Error('无法连接本地后端服务，请检查服务是否启动');
    throw error;
  } finally {
    window.clearTimeout(timer);
    init?.signal?.removeEventListener('abort', forwardAbort);
  }
}

const params = (values: Record<string, string | number | undefined>) => {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value));
  });
  return query.toString();
};

export const api = {
  records: async () => (await request<{ records: RecordSummary[] }>('/api/ecg/records')).records,
  models: async () => request<{ tasks: Record<TaskName, { labels: string[]; models: ModelStatus[] }> }>('/api/models'),
  window: (recordId: string, startSec: number, durationSec: number, leadName?: string, signal?: AbortSignal) =>
    request<WaveWindow>(`/api/ecg/window?${params({ record_id: recordId, start_sec: startSec, duration_sec: durationSec, lead_name: leadName })}`, { signal }),
  annotations: async (recordId: string, startSec: number, durationSec: number, task: TaskName, signal?: AbortSignal) =>
    (await request<{ annotations: BeatAnnotation[] }>(`/api/ecg/annotations?${params({ record_id: recordId, start_sec: startSec, duration_sec: durationSec, task })}`, { signal })).annotations,
  beat: (recordId: string, sample: number, task: TaskName, leadName?: string, signal?: AbortSignal) =>
    request<BeatDetail>(`/api/ecg/beat?${params({ record_id: recordId, annotation_sample: sample, task, lead_name: leadName })}`, {signal}),
  predict: (recordId: string, sample: number, task: TaskName, modelId: ModelId, signal?: AbortSignal) =>
    request<Prediction>('/api/inference/beat', { method: 'POST', signal, body: JSON.stringify({ record_id: recordId, annotation_sample: sample, task, model_id: modelId }) }),
  compare: (recordId: string, sample: number, task: TaskName, signal?: AbortSignal) =>
    request<{ task: TaskName; record_id: string; annotation_sample: number; expert_label: string; models: Prediction[]; all_models_agree: boolean; agreement_statement: string; probability_note: string }>('/api/inference/compare', { method: 'POST', signal, body: JSON.stringify({ record_id: recordId, annotation_sample: sample, task }) }),
  playback: (recordId: string, startSec: number, durationSec: number, task: TaskName, modelIds: ModelId[], leadName?: string, signal?: AbortSignal) => {
    const query = new URLSearchParams(params({ record_id: recordId, start_sec: startSec, duration_sec: durationSec, task, lead_name: leadName }));
    modelIds.forEach((id) => query.append('model_ids', id));
    return request<PlaybackSegment>(`/api/ecg/playback/segment?${query.toString()}`, {signal});
  },
};
