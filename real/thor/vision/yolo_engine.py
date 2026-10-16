"""Build the TensorRT engine that vision/person.py runs on the GPU, from an ONNX model. Run it on this Thor after a
JetPack or TensorRT change (an engine only works with the TensorRT version and GPU it was built with):

    .venv/bin/python vision/yolo_engine.py models/yolov8s.onnx models/yolov8s.engine      # about 100 s
"""
import sys

import tensorrt as trt


def build(onnx_path, engine_path):
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    net = builder.create_network(0)
    parser = trt.OnnxParser(net, logger)
    if not parser.parse(open(onnx_path, "rb").read()):
        for i in range(parser.num_errors):
            print("parse error:", parser.get_error(i))
        raise SystemExit(1)
    engine = builder.build_serialized_network(net, builder.create_builder_config())
    if engine is None:
        raise SystemExit("engine not built")
    open(engine_path, "wb").write(engine)
    print("wrote", engine_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])
