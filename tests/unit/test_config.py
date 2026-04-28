import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.config import Config, load_env_file


class TestConfig(unittest.TestCase):
    def test_parse_peers(self):
        self.assertEqual(Config.parse_peers("localhost:8002, localhost:8003"), ["localhost:8002", "localhost:8003"])
        self.assertEqual(Config.parse_peers(""), [])

    def test_load_env_file_and_from_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "NODE_ID=node9\nHOST=0.0.0.0\nADVERTISE_HOST=node9\nPORT=9009\nPEERS=node1:8001,node2:8002\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                load_env_file(env_path)
                config = Config.from_env()

        self.assertEqual(config["node_id"], "node9")
        self.assertEqual(config["bind_host"], "0.0.0.0")
        self.assertEqual(config["advertise_host"], "node9")
        self.assertEqual(config["port"], 9009)
        self.assertEqual(config["peers"], ["node1:8001", "node2:8002"])


if __name__ == "__main__":
    unittest.main()
