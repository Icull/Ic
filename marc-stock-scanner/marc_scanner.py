"""MARC: daily BEI momentum watchlist. Not investment advice."""
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
JAKARTA = ZoneInfo("Asia/Jakarta")
TOP_N = 10


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def load_universe():
    frame = pd.read_csv(ROOT / "universe.csv")
    frame = frame.dropna(subset=["ticker"])
    return [(str(row["ticker"]).strip().upper(), str(row.get("name", "")).strip())
            for _, row in frame.iterrows() if str(row["ticker"]).strip()]


def get_history(symbols):
    data = yf.download(
        tickers=[f"{symbol}.JK" for symbol in symbols],
        period="6mo", interval="1d", auto_adjust=True,
        group_by="ticker", threads=True, progress=False, timeout=25,
    )
    if data is None or data.empty:
        raise RuntimeError("Penyedia data tidak mengembalikan data harga.")
    return data


def score_stock(symbol, name, history):
    try:
        if isinstance(history.columns, pd.MultiIndex):
            ticker = f"{symbol}.JK"
            if ticker not in history.columns.get_level_values(0):
                return None
            frame = history[ticker].copy()
        else:
            frame = history.copy()
        if not {"Close", "Volume"}.issubset(set(frame.columns)):
            return None
        frame = frame[["Close", "Volume"]].dropna()
        frame = frame[frame["Close"] > 0]
        if len(frame) < 55:
            return None

        close = frame["Close"].astype(float)
        volume = frame["Volume"].astype(float)
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        strength = rsi(close)
        avg_volume = volume.rolling(20).mean()
        last_close, prev_close = float(close.iloc[-1]), float(close.iloc[-2])
        ret1 = (last_close / prev_close - 1) * 100
        ret5 = (last_close / float(close.iloc[-6]) - 1) * 100
        ret20 = (last_close / float(close.iloc[-21]) - 1) * 100
        last_ema20, last_ema50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
        last_rsi = float(strength.iloc[-1]) if pd.notna(strength.iloc[-1]) else 50.0
        mean_vol = float(avg_volume.iloc[-1]) if pd.notna(avg_volume.iloc[-1]) else 0.0
        vol_ratio = float(volume.iloc[-1] / mean_vol) if mean_vol > 0 else 0.0

        score, reasons = 0, []
        checks = [
            (last_close > last_ema20, 2, "harga di atas EMA20"),
            (last_ema20 > last_ema50, 2, "tren EMA20 > EMA50"),
            (ret5 > 0, 2, "momentum 5 hari positif"),
            (ret20 > 0, 1, "momentum 20 hari positif"),
            (vol_ratio >= 1.2, 2, "volume di atas rata-rata"),
            (50 <= last_rsi <= 70, 1, "RSI di zona momentum"),
            (ret1 > 0, 1, "kenaikan harian positif"),
        ]
        for passed, points, reason in checks:
            if passed:
                score += points
                reasons.append(reason)
        if last_rsi > 78:
            score -= 2
            reasons.append("risiko jenuh beli")
        if ret1 < -4:
            score -= 2
            reasons.append("tekanan turun harian")
        if vol_ratio < 0.25:
            score -= 1
            reasons.append("volume sangat tipis")
        return {
            "ticker": symbol, "name": name, "close": last_close,
            "ret1": ret1, "ret5": ret5, "ret20": ret20, "rsi": last_rsi,
            "vol_ratio": vol_ratio, "score": score,
            "date": frame.index[-1].strftime("%Y-%m-%d"), "reasons": reasons,
        }
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError):
        return None


def market_context():
    try:
        hist = yf.Ticker("^JKSE").history(period="10d", interval="1d")
        if hist is None or hist.empty or "Close" not in hist:
            return "IHSG: data tidak tersedia", ""
        closes = hist["Close"].dropna()
        latest = float(closes.iloc[-1])
        change = (latest / float(closes.iloc[-2]) - 1) * 100 if len(closes) >= 2 else 0.0
        return f"IHSG: {latest:,.2f} ({change:+.2f}%)", hist.index[-1].strftime("%Y-%m-%d")
    except Exception:
        return "IHSG: data tidak tersedia", ""


def format_report(ranked, market_line, market_date, report_time):
    dates = sorted({row["date"] for row in ranked})
    latest_date = dates[-1] if dates else "tidak tersedia"
    lines = [
        "📊 MARC | DAILY STOCK SCANNER",
        f"Waktu laporan: {report_time.strftime('%d %b %Y %H:%M WIB')}",
        f"Data harga terakhir: {latest_date}",
        market_line, "",
        "Top 10 kandidat momentum BEI (bukan kepastian harga naik):",
    ]
    for idx, row in enumerate(ranked[:TOP_N], start=1):
        lines.append(
            f"{idx}. {row['ticker']} — Rp{row['close']:,.0f} | Skor {row['score']}/11\n"
            f"   1D {row['ret1']:+.2f}% · 5D {row['ret5']:+.2f}% · "
            f"20D {row['ret20']:+.2f}% · RSI {row['rsi']:.0f} · Vol {row['vol_ratio']:.1f}x"
        )
        if row["reasons"]:
            lines.append("   " + ", ".join(row["reasons"][:3]))
    lines += [
        "",
        "Skor = ranking teknikal sederhana, bukan probabilitas naik.",
        "Periksa likuiditas, berita, dan risiko sebelum mengambil keputusan.",
        "Data Yahoo Finance dapat terlambat/tidak lengkap. Bukan nasihat investasi.",
    ]
    if market_date and market_date != latest_date:
        lines.insert(3, f"Catatan: tanggal data IHSG ({market_date}) berbeda dari saham.")
    return "\n".join(lines)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Secret TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID belum dikonfigurasi.")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=25,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("Telegram API gagal mengirim laporan.")


def main():
    now = datetime.now(JAKARTA)
    universe = load_universe()
    symbols = [symbol for symbol, _ in universe]
    names = dict(universe)
    history = get_history(symbols)
    ranked = [row for symbol in symbols
              if (row := score_stock(symbol, names[symbol], history)) is not None]
    if not ranked:
        raise RuntimeError("Tidak ada saham valid. Periksa koneksi dan data penyedia.")
    ranked.sort(key=lambda row: (row["score"], row["ret5"], row["vol_ratio"]), reverse=True)
    market_line, market_date = market_context()
    newest = max(row["date"] for row in ranked)
    newest_day = datetime.strptime(newest, "%Y-%m-%d").date()
    age_days = (now.date() - newest_day).days
    if age_days > 4:
        raise RuntimeError(f"Data saham terakhir {newest} terlalu lama ({age_days} hari). Laporan tidak dikirim.")
    report = format_report(ranked[:TOP_N], market_line, market_date, now)
    send_telegram(report)
    print(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MARC ERROR: {exc}", file=sys.stderr)
        raise
