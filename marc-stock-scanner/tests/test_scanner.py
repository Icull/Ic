import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import marc_scanner

class ScannerTests(unittest.TestCase):
    def test_rsi_handles_uptrend(self):
        values = pd.Series(np.linspace(100, 130, 40))
        result = marc_scanner.rsi(values)
        self.assertEqual(len(result), len(values))
        self.assertGreater(float(result.iloc[-1]), 50)

    def test_load_universe(self):
        universe = marc_scanner.load_universe()
        self.assertGreaterEqual(len(universe), 10)
        self.assertIn(("BBCA", "Bank Central Asia"), universe)
        self.assertTrue(all(symbol and ".JK" not in symbol for symbol, _ in universe))

    def test_multi_market_watchlists(self):
        stocks = marc_scanner.load_stock_universe()
        self.assertIn("BBCA.JK", [r[0] for r in stocks])
        self.assertIn("AAPL", [r[0] for r in stocks])
        self.assertGreaterEqual(len(stocks), 60)
        self.assertGreaterEqual(len(marc_scanner.load_market_csv(marc_scanner.CRYPTO_FILE)), 10)
        commodities = marc_scanner.load_market_csv(marc_scanner.COMMODITY_FILE)
        self.assertGreaterEqual(len(commodities), 8)
        self.assertIn(("GC=F", "Gold futures"), commodities)

    def test_score_stock(self):
        idx = pd.date_range("2025-01-01", periods=90, freq="B")
        frame = pd.DataFrame({"Close": np.linspace(100,150,90), "Volume": [100000.0]*90}, index=idx)
        result = marc_scanner.score_stock("TEST", "Synthetic Test", frame)
        self.assertIsNotNone(result)
        self.assertEqual(result["ticker"], "TEST")
        self.assertIn("score", result)
        self.assertGreater(result["ret5"], 0)

if __name__ == "__main__":
    unittest.main()
