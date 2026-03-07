"""Voxtral ASR backend (shakods/voxtral-asr-en). Requires: uv sync --extra audio."""

from __future__ import annotations

from pathlib import Path

from radioshaq.constants import ASR_LANGUAGE_AUTO

VOXTRAL_ASR_BASE_ID = "mistralai/Voxtral-Mini-3B-2507"
VOXTRAL_ASR_HF_MODEL_ID = "shakods/voxtral-asr-en"


class VoxtralASRBackend:
    """Transcribe using Voxtral (base: mistralai/Voxtral-Mini-3B-2507) with optional PEFT adapter."""

    def __init__(self) -> None:
        self._processor: object | None = None
        self._model: object | None = None

    def _load_base(self) -> tuple[object, object]:
        """Load base processor and model once; cache on instance."""
        if self._model is not None:
            assert self._processor is not None
            return self._processor, self._model
        try:
            import torch
            from transformers import AutoProcessor, VoxtralForConditionalGeneration
        except ImportError as e:
            raise RuntimeError(
                "Install ASR deps: uv sync --extra audio. Requires transformers, torch, mistral-common[audio]."
            ) from e
        self._processor = AutoProcessor.from_pretrained(VOXTRAL_ASR_BASE_ID)
        self._model = VoxtralForConditionalGeneration.from_pretrained(
            VOXTRAL_ASR_BASE_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        return self._processor, self._model

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

        import torch

        model_id = kwargs.get("model_id") or VOXTRAL_ASR_HF_MODEL_ID
        base_id = VOXTRAL_ASR_BASE_ID
        lang_normalized = (language or "").strip().lower()
        use_peft = (
            str(model_id).strip().lower() == VOXTRAL_ASR_HF_MODEL_ID.lower()
            and lang_normalized == "en"
        )

        processor, model = self._load_base()

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
