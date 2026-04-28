import unittest

from src.nodes.base_node import BaseNode


class FakeRequest:
    async def json(self):
        return {}


class TestOpenApiDocs(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])

    async def test_openapi_spec_contains_core_paths(self):
        spec = self.node.build_openapi_spec()

        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertIn("/lock/acquire", spec["paths"])
        self.assertIn("/queue/enqueue", spec["paths"])
        self.assertIn("/cache/status", spec["paths"])

    async def test_openapi_json_endpoint(self):
        resp = await self.node.openapi_json(FakeRequest())
        self.assertEqual(resp.status, 200)
        self.assertIn("openapi", resp.text)

    async def test_swagger_docs_endpoint(self):
        resp = await self.node.swagger_docs(FakeRequest())
        self.assertEqual(resp.status, 200)
        self.assertIn("SwaggerUIBundle", resp.text)


if __name__ == "__main__":
    unittest.main()
