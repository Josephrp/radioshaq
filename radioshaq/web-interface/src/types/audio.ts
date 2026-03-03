export enum ResponseMode {
  LISTEN_ONLY = 'listen_only',
  CONFIRM_FIRST = 'confirm_first',
  CONFIRM_TIMEOUT = 'confirm_timeout',
  AUTO_RESPOND = 'auto_respond',
}

export enum VADMode {
  NORMAL = 'normal',
  LOW_BITRATE = 'low',
  AGGRESSIVE = 'aggressive',
  VERY_AGGRESSIVE = 'very_aggressive',
}

export enum TriggerMatchMode {
  EXACT = 'exact',
  CONTAINS = 'contains',
  STARTS_WITH = 'starts_with',
  FUZZY = 'fuzzy',
}

export enum AudioActivationMode {
  SESSION = 'session',
  PER_MESSAGE = 'per_message',
}

export enum PendingResponseStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  EXPIRED = 'expired',
  AUTO_SENT = 'auto_sent',
}

export interface AudioConfig {
  input_device: string | number | null;
  input_sample_rate: number;
  output_device: string | number | null;
  preprocessing_enabled: boolean;
  agc_enabled: boolean;
  agc_target_rms: number;
  highpass_filter_enabled: boolean;
  highpass_cutoff_hz: number;
  denoising_enabled: boolean;
  denoising_backend: string;
  noise_calibration_seconds: number;
  min_snr_db: number;
  vad_enabled: boolean;
  vad_mode: string;
  pre_speech_buffer_ms: number;
  post_speech_buffer_ms: number;
  min_speech_duration_ms: number;
  max_speech_duration_ms: number;
  silence_duration_ms: number;
  asr_model: string;
  asr_language: string;
  asr_min_confidence: number;
  response_mode: ResponseMode;
  response_timeout_seconds: number;
  response_delay_ms: number;
  response_cooldown_seconds: number;
  trigger_enabled: boolean;
  trigger_phrases: string[];
  trigger_match_mode: TriggerMatchMode;
  trigger_callsign: string | null;
  trigger_min_confidence: number;
  audio_activation_enabled: boolean;
  audio_activation_phrase: string;
  audio_activation_mode: AudioActivationMode;
  ptt_coordination_enabled: boolean;
  ptt_cooldown_ms: number;
  break_in_enabled: boolean;
}

export interface PendingResponse {
  id: string;
  created_at: string;
  expires_at: string;
  incoming_transcript: string;
  incoming_audio_path: string | null;
  frequency_hz: number | null;
  mode: string | null;
  proposed_message: string;
  proposed_audio_path: string | null;
  status: PendingResponseStatus;
  responded_at: string | null;
  responded_by: string | null;
  notes: string | null;
}

export interface AudioDeviceInfo {
  index: number;
  name: string;
  channels: number;
  sample_rate?: number;
}

export interface AudioMetrics {
  session_id: string;
  type: string;
  vad_active?: boolean;
  snr_db?: number | null;
  state?: string;
}
