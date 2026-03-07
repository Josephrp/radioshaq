"""Voxtral ASR backend (shakods/voxtral-asr-en). Requires: uv sync --extra audio."""

from __future__ import annotations

from pathlib import Path

from radioshaq.constants import ASR_LANGUAGE_AUTO

VOXTRAL_ASR_HF_MODEL_ID = "shakods/voxtral-asr-en"


class VoxtralASRBackend:
    """Transcribe using Voxtral (base: mistralai/Voxtral-Mini-3B-2507) with optional PEFT adapter."""

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
        **kwargs: object,
    ) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(str(audio_path))

        try:
            import torch
            from transformers import AutoProcessor, VoxtralForConditionalGeneration
        except ImportError as e:
            raise RuntimeError(
                "Install ASR deps: uv sync --extra audio. Requires transformers, torch, mistral-common[audio]."
            ) from e

        model_id = kwargs.get("model_id") or VOXTRAL_ASR_HF_MODEL_ID
        base_id = "mistralai/Voxtral-Mini-3B-2507"
        lang_normalized = (language or "").strip().lower()
        use_peft = (
            str(model_id).strip().lower() == VOXTRAL_ASR_HF_MODEL_ID.lower()
            and lang_normalized == "en"
        )

        device_map = "auto"
        processor = AutoProcessor.from_pretrained(base_id)
        model = VoxtralForConditionalGeneration.from_pretrained(
            base_id,
            torch_dtype=torch.bfloat16,
            device_map=device_map,
        )

        if use_peft:
            try:
                from peft import PeftModel
                model = PeftModel.from_pretrained(model, VOXTRAL_ASR_HF_MODEL_ID)
                model.eval()
            except ImportError:
                pass  # PEFT not installed; run with base model
            except Exception as e:
                import warnings
                warnings.warn(
                    f"PEFT adapter load failed, using base model: {e}",
                    stacklevel=2,
                )

        if lang_normalized == ASR_LANGUAGE_AUTO:
            inputs = processor.apply_transcription_request(
                audio=str(path),
                model_id=base_id,
            )
        else:
            inputs = processor.apply_transcription_request(
                language=language or "en",
                audio=str(path),
                model_id=base_id,
            )
        inputs = inputs.to(model.device, dtype=torch.bfloat16)

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=500)
        decoded = processor.batch_decode(
            outputs[:, inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
        )
        return (decoded[0] if decoded else "").strip()
