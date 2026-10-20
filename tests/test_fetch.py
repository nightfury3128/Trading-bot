import pandas as pd

from data.fetch import _ConstituentsTableParser, _clean_tickers, split_bulk_ohlcv


def test_clean_tickers_normalizes_and_filters():
    assert _clean_tickers(["aapl", "BRK.B", "Symbol", "", "TOOLONGTICKER"]) == ["AAPL", "BRK-B"]


def test_wikipedia_parser_extracts_first_column():
    html = """
    <table id="constituents"><tbody>
      <tr><th>Symbol</th><th>Security</th></tr>
      <tr><td><a href="/wiki/Apple">AAPL</a></td><td>Apple</td></tr>
      <tr><td><a href="/wiki/Berkshire">BRK.B</a></td><td>Berkshire</td></tr>
    </tbody></table>
    """
    parser = _ConstituentsTableParser()
    parser.feed(html)
    assert _clean_tickers(row[0] for row in parser.rows if row) == ["AAPL", "BRK-B"]


def _ohlcv_frame(n=3, base=100.0):
    return pd.DataFrame({"Close": [base + i for i in range(n)], "Volume": [1_000] * n})


def test_split_bulk_ticker_first_columns():
    raw = pd.concat({"AAPL": _ohlcv_frame(), "MSFT": _ohlcv_frame(base=200.0)}, axis=1)
    out = split_bulk_ohlcv(raw, ["AAPL", "MSFT"])
    assert set(out) == {"AAPL", "MSFT"}
    assert out["MSFT"]["Close"].iloc[0] == 200.0


def test_split_bulk_field_first_columns():
    raw = pd.concat({"AAPL": _ohlcv_frame(), "MSFT": _ohlcv_frame(base=200.0)}, axis=1)
    raw = raw.swaplevel(0, 1, axis=1)
    out = split_bulk_ohlcv(raw, ["AAPL", "MSFT"])
    assert set(out) == {"AAPL", "MSFT"}


def test_split_bulk_empty_and_single():
    assert split_bulk_ohlcv(pd.DataFrame(), ["AAPL"]) == {}
    single = _ohlcv_frame()
    out = split_bulk_ohlcv(single, ["AAPL"])
    assert list(out) == ["AAPL"]
