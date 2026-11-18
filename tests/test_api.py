"""The service against its published contract (service/openapi.yaml), with a stub predictor.

Standard library only: no torch, no Laya, no weights, no network. PyYAML is used when it is
installed; otherwise the spec checks fall back to reading the file as text.
"""
import asyncio
import json
from pathlib import Path
import re
import unittest

from test_service import FakeAgent, cloud, request
from test_contract import state

SPEC_PATH = Path(__file__).resolve().parents[1] / "service" / "openapi.yaml"
APP_SOURCE = (Path(__file__).resolve().parents[1] / "service" / "app.py").read_text(encoding="utf-8")

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    yaml = None


def spec_schema(name):
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    return spec["components"]["schemas"][name]


class SpecMatchesCodeTest(unittest.TestCase):
    def test_every_error_code_in_the_code_is_documented(self):
        codes = set(re.findall(r'_HttpError\(\d+, "([a-z_]+)"', APP_SOURCE)) | {"request_failed"}
        self.assertEqual(len(codes), 10)
        if yaml is None:
            text = SPEC_PATH.read_text(encoding="utf-8")
            for code in codes:
                self.assertIn(code, text)
        else:
            self.assertEqual(set(spec_schema("Error")["properties"]["error"]["enum"]), codes)

    def test_limits_in_the_spec_match_the_contract(self):
        if yaml is None:
            self.skipTest("PyYAML not installed")
        props = spec_schema("State")["properties"]
        for key in ("message", "recent_context", "reference_text"):
            self.assertEqual(props[key]["maxLength"], 32768)
        self.assertEqual(props["attachments"]["maxItems"], 32)
        self.assertEqual(props["candidate_executors"]["maxItems"], 32)
        self.assertEqual(props["candidate_executors"]["items"]["maxLength"], 128)
        self.assertEqual(cloud.MAX_BODY, 65536)
        heads = spec_schema("Prediction")["properties"]["answers"]["required"]
        self.assertEqual(set(heads), set(cloud.contract.CHOICES))


class StubbedServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.agent = FakeAgent()
        self.now = 100.0
        runtime = cloud.Runtime(self.agent, {"task_type": {"type": "choice"}}, 874, "c" * 64, device="cpu")
        self.app = cloud.create_app(runtime, clock=lambda: self.now, log_sink=lambda record: None)
        await self.app.startup()

    async def asyncTearDown(self):
        self.agent.release.set()
        await self.app.shutdown()

    async def test_happy_path_returns_the_documented_fields(self):
        status, headers, body = await request(self.app, {"state": state("Translate hello to French.")})
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(set(body), {"modelVersion", "modelSha256", "device", "latencyMs", "raw", "region"})
        self.assertRegex(body["modelSha256"], r"^[0-9a-f]{64}$")
        self.assertIn("packed_state_tokens", body["raw"]["usage"])
        if yaml is not None:
            self.assertEqual(set(spec_schema("JudgeResponse")["required"]), set(body))
        status, _, health = await request(self.app, method="GET", path="/healthz", body=b"")
        self.assertEqual((status, set(health)), (200, {"modelVersion", "device", "queueLength"}))

    async def test_oversized_body_is_rejected_with_413(self):
        body = json.dumps({"state": state("x" * 70000)}).encode()
        status, _, result = await request(self.app, body)
        self.assertEqual((status, result), (413, {"error": "body_too_large"}))
        self.assertEqual(self.agent.calls, [])

    async def test_full_queue_returns_503_with_retry_after(self):
        self.agent.release.clear()
        running = asyncio.create_task(request(self.app))
        waiting = []
        try:
            async with asyncio.timeout(3):
                while not self.agent.entered.is_set():
                    await asyncio.sleep(0.005)
            waiting = [asyncio.create_task(request(self.app)) for _ in range(8)]
            async with asyncio.timeout(3):
                while self.app.queue_length < 8:
                    await asyncio.sleep(0.005)
            status, headers, result = await request(self.app)
            self.assertEqual((status, result), (503, {"error": "queue_full"}))
            self.assertEqual(headers[b"retry-after"], b"1")
        finally:
            self.agent.release.set()
            responses = await asyncio.gather(running, *waiting)
        self.assertTrue(all(response[0] == 200 for response in responses))


if __name__ == "__main__":
    unittest.main()
