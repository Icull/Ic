import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import marc_scanner


class ScannerTests(unittest.TestCase):
    def test_rsi_returns_series(self):
        values = pd.Series(np.linspace(100, 130, 40))
        result = marc_scanner.rsi(values)
        self.assertEqual(len(result), len(values))
        self.assertGreater(float(result.iloc[-1]), 50)

    def test_load_universe_contains_valid_pairs(self):
        universe = marc_scanner.load_universe()
        self.assertGreaterEqual(len(universe), 10)
        self.assertIn(("BBCA", "Bank Central Asia"), universe)
        self.assertTrue(all(symbol and ".JK" not in symbol for symbol, _ in universe))

    def test_score_stock_returns_rankable_record(self):
        idx = pd.date_range("2025-01-01", periods=90, freq="B")
        close = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
        volume = pd.Series([100000.0] * len(idx), index=idx)
        frame = pd.DataFrame({"Close": close, "Volume": volume})
        result = marc_scanner.score_stock("TEST", "Synthetic Test", frame)
        self.assertIsNotNone(result)
        self.assertEqual(result["ticker"], "TEST")
        self.assertIn("score", result)
        self.assertGreater(result["ret5"], 0)


if __name__ == "__main__":
    unittest.main()
