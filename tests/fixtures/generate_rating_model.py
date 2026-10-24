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

# Five-class style fixture: primary colors pass as illustration; cyan maps to
# 3D, black to not_painting. It tests routing without shipping real model weights.
graph = helper.make_graph(
    [helper.make_node("ReduceMean", ["input"], ["means"], axes=[2, 3], keepdims=0),
     helper.make_node("Gather", ["means", "gb_indices"], ["gb"], axis=1),
     helper.make_node("ReduceSum", ["gb", "sum_axes"], ["gb_sum"], keepdims=1),
     helper.make_node("Mul", ["gb_sum", "scale_3d"], ["logit_3d"]),
     helper.make_node("ReduceSum", ["means", "sum_axes"], ["all_sum"], keepdims=1),
     helper.make_node("Mul", ["all_sum", "scale_other"], ["logit_other"]),
     helper.make_node("Concat", ["logit_3d", "zero", "zero", "illustration", "logit_other"],
                      ["logits"], axis=1),
     helper.make_node("Softmax", ["logits"], ["output"], axis=1)],
    "style_gate",
    [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch", 3, "height", "width"])],
    [helper.make_tensor_value_info("output", TensorProto.FLOAT, ["batch", 5])],
    initializer=[helper.make_tensor("gb_indices", TensorProto.INT64, [2], [1, 2]),
                 helper.make_tensor("sum_axes", TensorProto.INT64, [1], [1]),
                 helper.make_tensor("scale_3d", TensorProto.FLOAT, [1, 1], [5]),
                 helper.make_tensor("scale_other", TensorProto.FLOAT, [1, 1], [-3]),
                 helper.make_tensor("zero", TensorProto.FLOAT, [1, 1], [0]),
                 helper.make_tensor("illustration", TensorProto.FLOAT, [1, 1], [6])],
)
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
onnx.checker.check_model(model)
onnx.save(model, Path(__file__).with_name("style_gate.onnx"))
