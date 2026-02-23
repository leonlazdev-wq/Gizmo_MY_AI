from __future__ import annotations

import ast
import operator as op
from typing import Any, Dict

from modules.tools.base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate arithmetic expressions safely."

    _ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
    }

    def _eval(self, node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._ops:
            return self._ops[type(node.op)](self._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self._ops:
            return self._ops[type(node.op)](self._eval(node.left), self._eval(node.right))
        raise ValueError("Unsupported expression")

    def execute(self, **kwargs) -> Dict[str, Any]:
        expr = str(kwargs.get("expression", "")).strip()
        if not expr:
            return {"ok": False, "error": "Missing expression"}

        try:
            node = ast.parse(expr, mode="eval").body
            return {"ok": True, "result": self._eval(node)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
