"""ASR using shakods/voxtral-asr-en (Voxtral fine-tune) via transformers."""

from __future__ import annotations

from pathlib import Path


def transcribe_audio_voxtral(
    audio_path: str | Path,
    model_id: str = "shakods/voxtral-asr-en",
    language: str = "en",
) -> str:
    """
    Transcribe audio file using Voxtral ASR (base: mistralai/Voxtral-Mini-3B-2507).

    When model_id is "shakods/voxtral-asr-en", loads the PEFT adapter on top of
    the base Voxtral model for English ASR.

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
    use_peft = model_id.strip().lower() == "shakods/voxtral-asr-en"

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
            model = PeftModel.from_pretrained(model, "shakods/voxtral-asr-en")
            model.eval()
        except ImportError:
            pass  # run without adapter
        except Exception:
            pass  # adapter load failed, use base

    # apply_transcription_request(language=..., audio=path, model_id=...) for transcription
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
