from hashlib import sha256
from io import BytesIO
from logging import getLogger
from math import isfinite, sqrt
from time import monotonic

from PIL import Image

from app.modules.ai.image_types import PROMPTS
from app.modules.ai.runtime import AIRuntime
from app.shared.errors import DomainError

logger = getLogger(__name__)

TEXT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TEXT_ONNX_REVISION = "a3ded7f4d0d725c6fc251504622d65b2516a3aa1"
IMAGE_MODEL = "ViT-B-32-quickgelu"
IMAGE_WEIGHTS = "openai"
TEXT_KEY = f"{TEXT_MODEL}:v1"
TEXT_ONNX_KEY = f"{TEXT_MODEL}:onnx:{TEXT_ONNX_REVISION}:v1"
IMAGE_KEY = f"{IMAGE_MODEL}:{IMAGE_WEIGHTS}:v1"


def embedding_key(model: str, value: str) -> str:
    return sha256(f"{model}\0{value}".encode()).hexdigest()


def cosine_similarity(first: list[float], second: list[float]) -> float:
    """Clamp negative cosine to zero."""
    if not first or len(first) != len(second):
        return 0.0
    norm = sqrt(sum(value * value for value in first) * sum(value * value for value in second))
    if not norm or not isfinite(norm):
        return 0.0
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    return min(1.0, max(0.0, dot / norm))


def text_vectors(runtime: AIRuntime, texts: list[str]) -> list[list[float]]:
    if monotonic() < runtime.text_model_retry_at:
        raise DomainError(503, "AI_MODEL_UNAVAILABLE", "Text embedding model unavailable")
    try:
        if runtime.text_backend == "onnx":
            from app.modules.ai.text_onnx import OnnxTextEncoder

            if runtime.text_model is None:
                runtime.text_model = OnnxTextEncoder(
                    TEXT_MODEL, TEXT_ONNX_REVISION, runtime.settings.ai_cpu_threads
                )
            return runtime.text_model.encode(texts)
        return torch_text_vectors(runtime, texts)
    except Exception as error:
        # External model loaders and runtimes define their own exception types.
        logger.warning(
            "Text embedding backend %s unavailable (%s)", runtime.text_backend, type(error).__name__
        )
        runtime.text_model = None
        runtime.text_model_retry_at = monotonic() + 60
        raise DomainError(503, "AI_MODEL_UNAVAILABLE", "Text embedding model unavailable") from None


def torch_text_vectors(runtime: AIRuntime, texts: list[str]) -> list[list[float]]:
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(runtime.settings.ai_cpu_threads)
    if runtime.text_model is None:
        runtime.text_model = SentenceTransformer(
            TEXT_MODEL, device="cpu", model_kwargs={"use_safetensors": True}
        )
    return runtime.text_model.encode(
        texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False
    ).tolist()


def predict_image_type(
    vector: list[float], prototypes: dict[str, list[float]], *, margin: float = 0.018
) -> str | None:
    scores = sorted(
        ((cosine_similarity(vector, example), kind) for kind, example in prototypes.items()),
        reverse=True,
    )
    if len(scores) < 2:
        return None
    (score, kind), (runner_up, _) = scores[:2]
    return kind if score >= 0.18 and score - runner_up >= margin else None


def image_vectors(runtime: AIRuntime, images: list[bytes]) -> list[list[float]]:
    try:
        import open_clip
        import torch

        torch.set_num_threads(runtime.settings.ai_cpu_threads)
        if runtime.image_model is None:
            model, _, transform = open_clip.create_model_and_transforms(
                IMAGE_MODEL, pretrained=IMAGE_WEIGHTS, device="cpu"
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer(IMAGE_MODEL)
            captions = [
                template.format(item)
                for item in PROMPTS.values()
                for template in ("a photo of {}", "a close-up photo showing {}")
            ]
            with torch.inference_mode():
                features = model.encode_text(tokenizer(captions), normalize=True)
                averaged = torch.nn.functional.normalize(
                    features.reshape(len(PROMPTS), 2, -1).mean(dim=1), dim=-1
                )
            runtime.image_prototypes = dict(zip(PROMPTS, averaged.tolist(), strict=True))
            runtime.image_model = (model.visual, transform)
            del model
        vision, transform = runtime.image_model
        inputs = []
        for data in images:
            with Image.open(BytesIO(data)) as image:
                pixels = image.convert("RGB")
                pixels.thumbnail((1024, 1024))
                inputs.append(transform(pixels))
        with torch.inference_mode():
            return torch.nn.functional.normalize(vision(torch.stack(inputs)), dim=-1).tolist()
    except (ImportError, OSError, ValueError, RuntimeError):
        raise DomainError(
            503, "AI_MODEL_UNAVAILABLE", "Image embedding model unavailable"
        ) from None
