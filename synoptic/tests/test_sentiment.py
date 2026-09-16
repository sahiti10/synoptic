import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import sentiment


class TestSentiment(unittest.TestCase):
    def test_negative_post(self):
        text = "<p>The tornado destroyed our roof, we are trapped and terrified.</p>"
        label, score = sentiment.score_text(text)
        self.assertEqual(label, "negative")
        self.assertLess(score, 0)

    def test_positive_post(self):
        text = "Everyone is safe, the storm passed and we're so grateful and thankful."
        label, score = sentiment.score_text(text)
        self.assertEqual(label, "positive")
        self.assertGreater(score, 0)

    def test_neutral_post(self):
        text = "The weather forecast for tomorrow mentions a chance of clouds."
        label, score = sentiment.score_text(text)
        self.assertEqual(label, "neutral")
        self.assertEqual(score, 0)

    def test_strip_html(self):
        cleaned = sentiment.strip_html("<p>Hello <b>world</b></p>")
        self.assertNotIn("<", cleaned)
        self.assertIn("Hello", cleaned)

    def test_negation_flips_sentiment(self):
        # "not safe" should not count as positive
        label, score = sentiment.score_text("We are not safe right now.")
        self.assertLessEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
