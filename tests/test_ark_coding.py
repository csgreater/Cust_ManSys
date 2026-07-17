from __future__ import annotations

import unittest

from app.ark_coding import _extract_content


class ArkCodingResponseTests(unittest.TestCase):
    def test_extracts_plain_text_content(self) -> None:
        body = {"choices": [{"message": {"content": "  可执行方案  "}}]}

        self.assertEqual(_extract_content(body), "可执行方案")

    def test_extracts_structured_text_content(self) -> None:
        body = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "第一步"},
                            {"type": "text", "text": "：验证"},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(_extract_content(body), "第一步：验证")

    def test_rejects_unexpected_provider_response(self) -> None:
        self.assertEqual(_extract_content({"choices": []}), "")
        self.assertEqual(_extract_content({"choices": [{"message": {"content": 42}}]}), "")


if __name__ == "__main__":
    unittest.main()
