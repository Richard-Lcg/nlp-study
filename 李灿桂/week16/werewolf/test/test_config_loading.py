import os
import unittest
from pathlib import Path

from config import load_config, get_llm_config, get_llm_config_cached


class TestConfigLoading(unittest.TestCase):
    def setUp(self):
        # 清除缓存
        from config import _llm_config
        import config
        config._llm_config = None

    def test_load_config_exists(self):
        cfg = load_config()
        self.assertIn("llm", cfg)

    def test_llm_config_has_keys(self):
        cfg = get_llm_config()
        self.assertIn("api_key", cfg)
        self.assertIn("model", cfg)
        self.assertIn("base_url", cfg)
        self.assertIn("max_tokens", cfg)

    def test_env_var_resolution(self):
        os.environ["TEST_LLM_KEY"] = "sk-test-resolved"
        file_path = Path(__file__).parent.parent / "config" / "config.yaml"
        original = file_path.read_text(encoding="utf-8")

        # 写入含 env var 引用的临时配置
        test_config = original.replace(
            'api_key: "sk-4f1e293d69ce4611830cf4386ab45cb3"',
            'api_key: "${TEST_LLM_KEY}"',
        )
        file_path.write_text(test_config, encoding="utf-8")

        from config import _llm_config
        import config
        config._llm_config = None
        cfg = get_llm_config()
        self.assertEqual(cfg["api_key"], "sk-test-resolved")

        # 恢复
        file_path.write_text(original, encoding="utf-8")
        del os.environ["TEST_LLM_KEY"]

    def test_caching(self):
        from config import _llm_config
        import config
        config._llm_config = None
        first = get_llm_config_cached()
        second = get_llm_config_cached()
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
