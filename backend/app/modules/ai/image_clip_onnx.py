import json
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image, ImageOps

from app.modules.ai.inference import predict_image_type

MODEL_ID = "Xenova/clip-vit-base-patch32"
REVISION = "6b7c523703ae26e39be4b03774966f8571c7f523"
MEAN = np.asarray([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.asarray([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)


class ClipImageClassifier:
    def __init__(self, threads: int):
        path = hf_hub_download(
            MODEL_ID, "onnx/vision_model_q4.onnx", revision=REVISION, token=False
        )
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        self.session = ort.InferenceSession(
            path, sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.prototypes = json.loads(
            Path(__file__).with_name("clip_image_prototypes.json").read_text(encoding="utf-8")
        )

    def classify(self, data: bytes) -> str | None:
        with Image.open(BytesIO(data)) as source:
            crop = ImageOps.fit(source.convert("RGB"), (224, 224), Image.Resampling.BICUBIC)
            rgb = np.asarray(crop, dtype=np.float32) / 255
        pixels = np.ascontiguousarray(((rgb - MEAN) / STD).transpose(2, 0, 1)[None])
        (vector,) = self.session.run(["image_embeds"], {self.input_name: pixels})
        return predict_image_type(vector.flatten().tolist(), self.prototypes, margin=0.045)
