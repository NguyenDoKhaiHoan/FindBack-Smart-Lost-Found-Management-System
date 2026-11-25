from platform import machine

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MAX_TOKENS = 128


class OnnxTextEncoder:
    def __init__(self, model_id: str, revision: str, threads: int):
        architecture = machine().lower()
        file = (
            "model_qint8_arm64.onnx"
            if architecture in {"arm64", "aarch64"}
            else "model_quint8_avx2.onnx"
        )
        tokenizer_path = hf_hub_download(model_id, "tokenizer.json", revision=revision, token=False)
        model_path = hf_hub_download(model_id, f"onnx/{file}", revision=revision, token=False)
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"))

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        self.session = ort.InferenceSession(
            model_path, sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_names = {field.name for field in self.session.get_inputs()}

    def encode(self, texts: list[str]) -> list[list[float]]:
        result = []
        for start in range(0, len(texts), 8):
            tokens = self.tokenizer.encode_batch(texts[start : start + 8])
            values = {
                "input_ids": [row.ids for row in tokens],
                "attention_mask": [row.attention_mask for row in tokens],
                "token_type_ids": [row.type_ids for row in tokens],
            }
            batch = {name: np.asarray(values[name], dtype=np.int64) for name in self.input_names}
            (hidden,) = self.session.run(["last_hidden_state"], batch)
            mask = np.asarray(values["attention_mask"], dtype=np.float32)[..., None]
            pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
            unit = pooled / np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)
            result.extend(unit.tolist())
        return result
