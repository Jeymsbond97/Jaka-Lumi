"""Supertonic's vector estimator and vocoder (nearly all of the TTS time) on the GPU through TensorRT.

    .venv/bin/python audio/tts_gpu.py build     # once on this Thor, after a JetPack / TensorRT change (~90 s)
    .venv/bin/python audio/tts_gpu.py check     # GPU against CPU: time and difference on a few sentences

On the CPU the vector estimator takes 0.1-0.27 s per step (4 steps a sentence) and the vocoder 0.06-0.17 s. mouth.py
puts Engine in place of the onnxruntime sessions when the engine files load, else the CPU stays (it says why).
The engines are bound to this Thor's TensorRT and GPU, like models/yolov8s.engine.
"""
import pathlib
import sys
import threading
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
MODELS = {"vector_estimator": "vector_est_ort", "vocoder": "vocoder_ort"}   # file -> attribute in supertonic's model;
                                                 # the text encoder and durations take ~20 ms, they stay on the CPU
MAX_LEN = 640                    # text / latent frames the engine takes (latent ~14.5 frames per s of speech:
                                 # 44 s; a TTS chunk is at most 300 characters). Longer: the CPU session


def onnx(name):
    return ROOT / f"models/supertonic3/onnx/{name}.onnx"


def engine_file(name):
    return ROOT / f"models/supertonic3_{name}.engine"


def build(name):
    import tensorrt as trt
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    net = builder.create_network(0)
    parser = trt.OnnxParser(net, logger)
    if not parser.parse_from_file(str(onnx(name))):
        raise SystemExit("\n".join(str(parser.get_error(i)) for i in range(parser.num_errors)))
    cfg = builder.create_builder_config()
    cfg.set_flag(trt.BuilderFlag.TF32)
    prof = builder.create_optimization_profile()
    for i in range(net.num_inputs):              # batch 1; text_length / latent_length 1 ... MAX_LEN
        t = net.get_input(i)
        dims = [list(t.shape) for _ in range(3)]
        for j, d in enumerate(t.shape):
            if d == -1:
                dims[0][j], dims[1][j], dims[2][j] = (1, 1, 1) if j == 0 else (1, 80, MAX_LEN)
        prof.set_shape(t.name, *dims)
    cfg.add_optimization_profile(prof)
    engine = builder.build_serialized_network(net, cfg)
    if engine is None:
        raise SystemExit("engine not built")
    engine_file(name).write_bytes(engine)
    print("wrote", engine_file(name))


class Engine:
    """Drop-in for the onnxruntime session: run(None, feed) -> [output]. Inputs longer than MAX_LEN go to `cpu`."""

    def __init__(self, name, cpu):
        import tensorrt as trt
        from cuda.bindings import runtime as cr
        self.cr, self.cpu = cr, cpu
        self.engine = trt.Runtime(trt.Logger(trt.Logger.ERROR)).deserialize_cuda_engine(engine_file(name).read_bytes())
        if self.engine is None:
            raise RuntimeError(f"cannot load {engine_file(name)}")
        self.ctx = self.engine.create_execution_context()
        self.names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
        self.out = next(n for n in self.names if self.engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
        self.stream = self._ok(cr.cudaStreamCreate())
        self.dev = {}                            # name -> (device pointer, bytes), grown when needed
        self.lock = threading.Lock()             # one run at a time (a skill's result is spoken from another thread)

    def _ok(self, r):
        err, *val = r if isinstance(r, tuple) else (r,)
        if err != self.cr.cudaError_t.cudaSuccess:
            raise RuntimeError(f"CUDA error {err}")
        return val[0] if val else None

    def _buf(self, name, nbytes):
        ptr, size = self.dev.get(name, (None, 0))
        if size < nbytes:
            if ptr is not None:
                self._ok(self.cr.cudaFree(ptr))
            ptr, size = self._ok(self.cr.cudaMalloc(nbytes)), nbytes
            self.dev[name] = (ptr, size)
        self.ctx.set_tensor_address(name, int(ptr))
        return ptr

    def run(self, _outputs, feed):
        if any(x.shape[0] != 1 or x.shape[-1] > MAX_LEN for x in feed.values()):   # the lengths are the last axis
            return self.cpu.run(_outputs, feed)
        with self.lock:
            return self._run(feed)

    def _run(self, feed):
        cr = self.cr
        h2d, d2h = cr.cudaMemcpyKind.cudaMemcpyHostToDevice, cr.cudaMemcpyKind.cudaMemcpyDeviceToHost
        keep = []                                # host arrays stay alive until the copies are done
        for name, x in feed.items():
            x = np.ascontiguousarray(x, np.float32)
            keep.append(x)
            self.ctx.set_input_shape(name, x.shape)
            self._ok(cr.cudaMemcpyAsync(self._buf(name, x.nbytes), x.ctypes.data, x.nbytes, h2d, self.stream))
        out = np.empty(tuple(self.ctx.get_tensor_shape(self.out)), np.float32)
        ptr = self._buf(self.out, out.nbytes)
        if not self.ctx.execute_async_v3(int(self.stream)):
            raise RuntimeError("TensorRT run failed")
        self._ok(cr.cudaMemcpyAsync(out.ctypes.data, ptr, out.nbytes, d2h, self.stream))
        self._ok(cr.cudaStreamSynchronize(self.stream))
        return [out]


def use(model):
    """Put the GPU engines into a loaded supertonic model (TTS().model). Raises when an engine does not load."""
    for name, attr in MODELS.items():
        cpu = getattr(model, attr)
        if not isinstance(cpu, Engine):
            setattr(model, attr, Engine(name, cpu))


def check():
    """Each sentence on the CPU and on the GPU (same noise): synthesis time and the difference in the sound."""
    from audio import mouth
    mouth._set_volume = lambda: None             # nothing is played or changed
    tts = mouth._load()
    m = tts.model
    use(m)                                       # mouth.py has done it when the engines load
    gpu = {a: getattr(m, a) for a in MODELS.values()}
    cpu = {a: e.cpu for a, e in gpu.items()}
    for s in ["Lumi.", "I was developed by Cutshion Company.", "고마워요! 그렇게 말씀해 주시니 기쁘네요.",
              "I can talk with you in English and Korean, answer questions about Cutshion, and guide you around."]:
        wavs = []
        for sessions in (cpu, gpu):
            for a, sess in sessions.items():
                setattr(m, a, sess)
            np.random.seed(0)
            t = time.time()
            wav, _ = tts.synthesize(s, voice_style=mouth._style, lang=mouth.lang_of(s), total_steps=mouth.STEPS,
                                    speed=mouth.speed())
            wavs.append((time.time() - t, wav.reshape(-1)))
        (tc, a), (tg, b) = wavs
        n = min(len(a), len(b))
        print(f"cpu {tc:4.2f} s  gpu {tg:4.2f} s  max diff {np.abs(a[:n] - b[:n]).max():.4f}  "
              f"rms diff / rms {np.sqrt(np.mean((a[:n] - b[:n]) ** 2)) / np.sqrt(np.mean(a[:n] ** 2)):.4f}  {s[:40]}")


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        for n in MODELS:
            build(n)
    elif sys.argv[1:] == ["check"]:
        from audio import tts_gpu                # the module mouth.py loads, not __main__ (another Engine class)
        tts_gpu.check()
    else:
        sys.exit(__doc__)
