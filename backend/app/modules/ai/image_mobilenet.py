from io import BytesIO

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image, ImageOps

from app.modules.ai.inference import cosine_similarity

MODEL_ID = "onnxmodelzoo/mobilenetv2-12-int8"
REVISION = "b5c248f66acc836ca8893c58229b00d2520c388b"
KEY = f"{MODEL_ID}:{REVISION}:v1"
CLASS_COUNT = 1000
THUMBNAIL_SIZE = 8 * 8 * 3
# ImageNet class indices used by this model.
CLASSES = {
    "backpack": (414,),
    "phone": (487,),
    "laptop": (620, 681),
    "watch": (531,),
    "camera": (732, 759),
    "bag": (748,),
    "glasses": (836, 837),
    "umbrella": (879,),
    "wallet": (893,),
    "bottle": (898,),
    "book": (921,),
}


class MobileImageEncoder:
    def __init__(self, threads: int):
        path = hf_hub_download(MODEL_ID, "mobilenetv2-12-int8.onnx", revision=REVISION, token=False)
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            path, sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)

    def encode(self, images: list[bytes]) -> list[list[float]]:
        vectors = []
        for data in images:
            with Image.open(BytesIO(data)) as original:
                image = original.convert("RGB")
                crop = ImageOps.fit(image, (224, 224), Image.Resampling.BILINEAR)
                thumbnail = list(crop.resize((8, 8), Image.Resampling.BOX).tobytes())
                grayscale = np.asarray(crop.convert("L").resize((9, 8), Image.Resampling.BOX))
                edges = (grayscale[:, 1:] > grayscale[:, :-1]).ravel().astype(int).tolist()
            rgb = np.asarray(crop, dtype=np.float32) / 255
            image_input = np.ascontiguousarray(((rgb - self.mean) / self.std).transpose(2, 0, 1))
            (output,) = self.session.run(None, {self.input_name: image_input[None]})
            logits = output.reshape(CLASS_COUNT)
            weights = np.exp(logits - logits.max())
            probabilities = (weights / weights.sum()).round(6).tolist()
            vectors.append([*probabilities, *thumbnail, *edges])
        return vectors


def classify(vector: list[float]) -> str | None:
    ranked = sorted(
        ((sum(vector[index] for index in indices), label) for label, indices in CLASSES.items()),
        reverse=True,
    )
    (confidence, kind), (next_confidence, _) = ranked[:2]
    return kind if confidence >= 0.18 and confidence - next_confidence >= 0.08 else None


def likeness(first: list[float], second: list[float]) -> float:
    semantic = cosine_similarity(first[:CLASS_COUNT], second[:CLASS_COUNT])
    edge_start = CLASS_COUNT + THUMBNAIL_SIZE
    pixels = first[CLASS_COUNT:edge_start]
    difference = sum(
        abs(left - right)
        for left, right in zip(pixels, second[CLASS_COUNT:edge_start], strict=True)
    ) / (len(pixels) * 255)
    edges = first[edge_start:]
    structure = sum(a == b for a, b in zip(edges, second[edge_start:], strict=True)) / len(edges)
    visual = 1 - difference
    score = 0.75 * semantic + 0.25 * visual
    if difference <= 0.045 and structure >= 0.90 and 0 < sum(edges) < len(edges):
        return 0.92 + 0.08 * (structure + visual) / 2
    return min(0.91, score)
