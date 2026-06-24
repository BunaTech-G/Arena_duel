import unittest

from game.score_formatter import format_score_value


class ScoreFormatterTests(unittest.TestCase):
    def test_grouped_mode_keeps_scores_readable(self):
        cases = {
            0: "0",
            1: "1",
            30: "30",
            98: "98",
            114: "114",
            293: "293",
            6745: "6 745",
            78698: "78 698",
            9999999: "9 999 999",
        }

        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(format_score_value(raw_value), expected)

    def test_compact_mode_supports_large_scores(self):
        cases = {
            6745: "6.7k",
            78698: "78.7k",
            1200000: "1.2M",
            9999999: "10M",
        }

        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(
                    format_score_value(raw_value, mode="compact"),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
