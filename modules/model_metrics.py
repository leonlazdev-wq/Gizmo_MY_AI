"""Model/system performance dashboard helpers."""

from __future__ import annotations

import html
import threading
import time
from collections import deque
from typing import Deque, Dict, List

import psutil

try:
    import GPUtil
except Exception:  # pragma: no cover
    GPUtil = None


class ModelMetrics:
    def __init__(self) -> None:
        self.metrics_history: Deque[Dict[str, float]] = deque(maxlen=300)
        self.is_monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start_monitoring(self) -> str:
        if self.is_monitoring:
            return "ℹ️ Metrics monitor already running"
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return "✅ Metrics monitoring started"

    def stop_monitoring(self) -> str:
        self.is_monitoring = False
        return "⏹️ Metrics monitoring stopped"

    def _monitor_loop(self) -> None:
        while self.is_monitoring:
            self.collect_current_metrics()
            time.sleep(1.0)

    def collect_current_metrics(self) -> Dict[str, float]:
        vm = psutil.virtual_memory()
        metrics: Dict[str, float] = {
            "timestamp": time.time(),
            "ram_used_gb": vm.used / (1024**3),
            "ram_percent": vm.percent,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
        }
        if GPUtil is not None:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    metrics["gpu_used_mb"] = float(gpu.memoryUsed)
                    metrics["gpu_total_mb"] = float(gpu.memoryTotal)
                    metrics["gpu_percent"] = (float(gpu.memoryUsed) / max(1.0, float(gpu.memoryTotal))) * 100.0
                    metrics["gpu_temperature"] = float(getattr(gpu, "temperature", 0.0) or 0.0)
            except Exception:
                pass

        with self._lock:
            self.metrics_history.append(metrics)
        return metrics

    def get_history(self) -> List[Dict[str, float]]:
        with self._lock:
            return list(self.metrics_history)

    @staticmethod
    def get_tokens_per_second(generation_time: float, token_count: int) -> float:
        if generation_time <= 0:
            return 0.0
        return token_count / generation_time

    def generate_dashboard_html(self) -> str:
        if not self.metrics_history:
            self.collect_current_metrics()
        latest = self.get_history()[-1]
        ram_pct = min(100.0, max(0.0, latest.get("ram_percent", 0.0)))
        cpu_pct = min(100.0, max(0.0, latest.get("cpu_percent", 0.0)))
        html_block = f"""
        <div style='font-family:monospace;background:#1e1e1e;padding:16px;border-radius:10px'>
          <h3 style='color:#4CAF50;margin-top:0'>⚡ Real-Time Metrics</h3>
          <div><strong style='color:#ddd'>RAM</strong> <span style='color:#999'>{latest.get('ram_used_gb', 0):.1f} GB ({ram_pct:.1f}%)</span></div>
          <div style='width:100%;height:8px;background:#333;border-radius:4px'><div style='width:{ram_pct}%;height:100%;background:linear-gradient(90deg,#4CAF50,#FFC107,#F44336)'></div></div>
          <div style='margin-top:10px'><strong style='color:#ddd'>CPU</strong> <span style='color:#999'>{cpu_pct:.1f}%</span></div>
          <div style='width:100%;height:8px;background:#333;border-radius:4px'><div style='width:{cpu_pct}%;height:100%;background:#2196F3'></div></div>
        """
        if "gpu_percent" in latest:
            gpu_pct = min(100.0, max(0.0, latest.get("gpu_percent", 0.0)))
            html_block += f"""
            <div style='margin-top:10px'><strong style='color:#ddd'>GPU VRAM</strong> <span style='color:#999'>{latest.get('gpu_used_mb', 0):.0f}/{latest.get('gpu_total_mb', 0):.0f} MB ({gpu_pct:.1f}%)</span></div>
            <div style='width:100%;height:8px;background:#333;border-radius:4px'><div style='width:{gpu_pct}%;height:100%;background:linear-gradient(90deg,#9C27B0,#FF4081)'></div></div>
            <div style='margin-top:8px;color:#bbb'>GPU Temp: {latest.get('gpu_temperature', 0):.0f}°C</div>
            """
        html_block += "</div>"
        return html.unescape(html_block)


METRICS = ModelMetrics()
