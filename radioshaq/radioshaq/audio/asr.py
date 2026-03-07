"""ASR using Voxtral fine-tune (HF repo: shakods/voxtral-asr-en) via transformers."""

from __future__ import annotations

from pathlib import Path

from radioshaq.constants import ASR_LANGUAGE_AUTO

# Hugging Face repo ID for RadioShaq English ASR adapter (legacy org name on HF).
VOXTRAL_ASR_HF_MODEL_ID = "shakods/voxtral-asr-en"


def transcribe_audio_voxtral(
    audio_path: str | Path,
    model_id: str = VOXTRAL_ASR_HF_MODEL_ID,
    language: str = "en",
) -> str:
    """
    Transcribe audio file using Voxtral ASR (base: mistralai/Voxtral-Mini-3B-2507).

    Language behavior:
    - "auto": no language is passed to the processor; the base model does automatic
      language detection (Voxtral supports 13 languages). The English PEFT adapter
      is not loaded so multilingual/auto works correctly.
    - "en", "fr", "es": passed to the processor. For "en" only, the RadioShaq
      PEFT adapter (voxtral-asr-en) is loaded for better English accuracy; for
      "fr"/"es" the base model is used so transcription works for those languages.

    When model_id is the RadioShaq Voxtral ASR HF repo and language is "en", loads
    the PEFT adapter on top of the base model for best English ASR.

    Requires: transformers, peft, accelerate, torch, mistral-common[audio]
    (install with: uv sync --extra audio)
    """
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

    base_id = "mistralai/Voxtral-Mini-3B-2507"
    lang_normalized = (language or "").strip().lower()
    # Only use the English PEFT adapter when language is explicitly English;
    # for auto/fr/es use base model so multilingual and auto-detect work correctly.
    use_peft = (
        model_id.strip().lower() == VOXTRAL_ASR_HF_MODEL_ID.lower()
        and lang_normalized == "en"
    )

    device_map = "auto"  # uses GPU if available, else CPU
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
            pass  # run without adapter
        except Exception:
            pass  # adapter load failed, use base

    # Omit language for auto-detect (base Voxtral supports 13 languages + auto-detect)
    if lang_normalized == ASR_LANGUAGE_AUTO:
        inputs = processor.apply_transcription_request(
            audio=str(path),
            model_id=base_id,
        )
    else:
        inputs = processor.apply_transcription_request(
            language=language,
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
