import unittest
import numpy as np
from strategy.allocator import SmartAllocator
from unittest.mock import patch

class TestSmartAllocator(unittest.TestCase):
    def test_allocator_normalization(self):
        """Verify weights sum to 1."""
        tickers = ["AAPL", "TSLA", "MSFT"]
        scores = {"AAPL": 0.1, "TSLA": 0.05, "MSFT": 0.02}
        volomap = {"AAPL": 0.1, "TSLA": 0.2, "MSFT": 0.05}
        total_capital = 1000.0
        
        with patch('strategy.allocator.get_industry', return_value="Tech"):
            allocator = SmartAllocator(tickers, scores, volomap, total_capital)
            allocation = allocator.allocate()
            
            weights = list(allocation.values())
            self.assertAlmostEqual(sum(weights), 1.0)

    def test_allocator_ranking(self):
        """Verify higher score leads to higher allocation."""
        tickers = ["A", "B"]
        scores = {"A": 0.2, "B": 0.1}
        volomap = {"A": 0.1, "B": 0.1}
        
        with patch('strategy.allocator.get_industry', return_value="Common"):
            allocator = SmartAllocator(tickers, scores, volomap, 1000.0)
            allocation = allocator.allocate()
            
            self.assertGreater(allocation["A"], allocation["B"])

    def test_max_position_cap(self):
        """Verify max weight per stock is 0.2 when plenty of stocks available."""
        # 10 stocks, one is a "Winner" with huge score
        tickers = ["Winner"] + [f"Stock{i}" for i in range(9)]
        scores = {"Winner": 10.0}
        scores.update({f"Stock{i}": 0.01 for i in range(9)})
        volomap = {t: 0.1 for t in tickers}
        
        with patch('strategy.allocator.get_industry', return_value="Misc"):
            allocator = SmartAllocator(tickers, scores, volomap, 1000.0, max_stock_cap=0.2)
            allocation = allocator.allocate()
            
            # Winner should get at most 20%
            self.assertLessEqual(allocation["Winner"], 0.200001)

if __name__ == '__main__':
    unittest.main()
