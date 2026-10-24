"""Regenerate tiny, weight-free fixture: uv run --no-project --with onnx==1.23.2 <this file>."""
from pathlib import Path

import onnx
from onnx import TensorProto, helper

graph = helper.make_graph(
    [helper.make_node("ReduceMean", ["input"], ["means"], axes=[2, 3], keepdims=0),
     helper.make_node("Softmax", ["means"], ["output"], axis=1)],
    "three_channel_means",
    [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch", 3, "height", "width"])],
    [helper.make_tensor_value_info("output", TensorProto.FLOAT, ["batch", 3])],
)
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
onnx.checker.check_model(model)
onnx.save(model, Path(__file__).with_name("rating_channel_means.onnx"))
