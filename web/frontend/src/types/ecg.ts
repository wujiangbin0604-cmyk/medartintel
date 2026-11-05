export type TaskName = 'nv' | 'nsvf';
export type ModelId = 'logistic_regression' | 'random_forest' | 'cnn_1d';
export type AamiLabel = 'N' | 'S' | 'V' | 'F' | 'Q';

export interface RecordSummary {
  record_id: string;
  sampling_frequency: number;
  duration_seconds: number;
  sample_count: number;
  signal_names: string[];
  signal_units: string[];
  available_annotations: Record<string, number>;
  annotation_count: number;
  dataset_split: string;
  subject_id: string;
  model_inference_available: boolean;
  model_inference_reason: string | null;
}

export interface WavePoint { sample_index: number; time_seconds: number; amplitude_mv: number }
export interface WaveWindow {
  record_id: string; lead_name: string; sampling_frequency: number; unit: string;
  start_seconds: number; end_seconds: number; start_sample: number;
  stop_sample_exclusive: number; point_count: number; points: WavePoint[]; downsampled: boolean;
}

export interface BeatAnnotation {
  record_id: string; annotation_sample: number; time_seconds: number;
  original_label: string; annotation_kind: string; aami_label: string | null;
  within_task: boolean | null; lead_name: string;
  prediction_eligible?: boolean; prediction_unavailable_reason?: string | null;
  predictions?: Prediction[];
}

export interface BeatDetail {
  record_id: string; subject_id: string; dataset_split: string; annotation_sample: number;
  time_seconds: number; lead_name: string; sampling_frequency: number; unit: string;
  original_label: string; aami_label: AamiLabel; task: TaskName; within_task: boolean;
  window_start_sample: number; window_stop_sample_exclusive: number;
  window_time_relative_seconds: number[]; raw_amplitude_mv: number[]; filtered_amplitude_mv: number[];
  inference_eligible: boolean; inference_unavailable_reason: string | null;
  normalized_model_input: null;
}

export interface Prediction {
  task: TaskName; model_id: ModelId; record_id: string; annotation_sample: number;
  predicted_class: string; class_probabilities: Record<string, number>; expert_label: string;
  prediction_matches_expert: boolean; inference_time_ms: number; model_version: string;
  model_sha256: string; preprocessing_version: string; prediction_source: string;
  lead_name: string; dataset_split: string; probability_note: string;
}

export interface ModelStatus {
  task: TaskName; model_id: ModelId; loaded: boolean; error?: string | null;
  labels: string[]; model_version?: string; model_sha256?: string;
  checkpoint_path?: string; input_length?: number; device?: string;
  probability_source?: string;
}

export interface PlaybackSegment {
  record_id: string; task: TaskName; model_ids: ModelId[]; start_sec: number; duration_sec: number;
  historical_recording: true; real_time_monitoring: false; notice: string;
  waveform: WaveWindow; annotations: BeatAnnotation[]; expert_beat_count: number;
  predicted_beat_count: number; prediction_model_rows: number;
}

export const MODEL_LABELS: Record<ModelId, string> = {
  logistic_regression: 'Logistic Regression',
  random_forest: 'Random Forest',
  cnn_1d: '1D-CNN',
};
