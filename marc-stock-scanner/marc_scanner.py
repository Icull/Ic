"""MARC multi-market scanner: stocks, crypto and commodities."""
import os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
JAKARTA = ZoneInfo("Asia/Jakarta")
TOP_N = 10
GLOBAL_STOCKS_FILE = ROOT / "global_stocks.csv"
CRYPTO_FILE = ROOT / "crypto_universe.csv"
COMMODITY_FILE = ROOT / "commodity_universe.csv"

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    result = result.mask(loss == 0, 100.0).mask((gain == 0) & (loss == 0), 50.0)
    return result.fillna(50.0)

def load_universe():
    frame = pd.read_csv(ROOT / "universe.csv").dropna(subset=["ticker"])
    return [(str(r["ticker"]).strip().upper(), str(r.get("name", "")).strip())
            for _, r in frame.iterrows() if str(r["ticker"]).strip()]

def load_market_csv(path):
    frame = pd.read_csv(path).dropna(subset=["ticker"])
    return [(str(r["ticker"]).strip().upper(), str(r.get("name", "")).strip())
            for _, r in frame.iterrows() if str(r["ticker"]).strip()]

def load_stock_universe():
    rows = [(f"{t}.JK", n, "Indonesia") for t, n in load_universe()]
    rows += [(t, n, "Global") for t, n in load_market_csv(GLOBAL_STOCKS_FILE)]
    result, seen = [], set()
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0]); result.append(row)
    return result

def extract_symbol(data, symbol):
    if data is None or data.empty: return pd.DataFrame()
    if not isinstance(data.columns, pd.MultiIndex): return data.copy()
    for level in (0, 1):
        if symbol in data.columns.get_level_values(level):
            try:
                frame = data.xs(symbol, axis=1, level=level, drop_level=True)
                if isinstance(frame.columns, pd.MultiIndex): frame.columns = frame.columns.get_level_values(-1)
                return frame.copy()
            except (KeyError, ValueError): pass
    return pd.DataFrame()

def download_history(symbols, period="6mo", interval="1d"):
    if not symbols: return None
    return yf.download(tickers=symbols, period=period, interval=interval, auto_adjust=True,
                       group_by="ticker", threads=True, progress=False, timeout=25)

def score_stock(symbol, name, history, region=""):
    try:
        frame = history.copy()
        if not {"Close", "Volume"}.issubset(frame.columns): return None
        frame = frame[["Close", "Volume"] + (["High", "Low"] if {"High","Low"}.issubset(frame.columns) else [])].dropna()
        frame = frame[frame.Close > 0]
        if len(frame) < 55: return None
        close, volume = frame.Close.astype(float), frame.Volume.astype(float)
        ema20, ema50 = close.ewm(span=20, adjust=False).mean(), close.ewm(span=50, adjust=False).mean()
        strength, avgvol = rsi(close), volume.rolling(20).mean()
        price, prev = float(close.iloc[-1]), float(close.iloc[-2])
        ret1, ret5, ret20 = (price/prev-1)*100, (price/float(close.iloc[-6])-1)*100, (price/float(close.iloc[-21])-1)*100
        av = float(avgvol.iloc[-2]) if len(avgvol)>1 and pd.notna(avgvol.iloc[-2]) else 0
        vr = float(volume.iloc[-1]/av) if av>0 else 0
        rng = ((frame.High.iloc[-20:].max()-frame.Low.iloc[-20:].min())/price*100) if {"High","Low"}.issubset(frame.columns) else abs(ret5)
        checks = [(price>ema20.iloc[-1],2,"harga di atas EMA20"),(ema20.iloc[-1]>ema50.iloc[-1],2,"tren EMA20 > EMA50"),
                  (ret5>0,2,"momentum 5 hari positif"),(ret20>0,1,"momentum 20 hari positif"),
                  (vr>=1.2,2,"volume di atas rata-rata"),(50<=strength.iloc[-1]<=70,1,"RSI momentum"),
                  (abs(ret1)>=1.5 or rng>=5,1,"potensi volatilitas")]
        score, reasons = sum(p for ok,p,_ in checks if ok), [s for ok,_,s in checks if ok]
        if strength.iloc[-1]>78: score-=2; reasons.append("risiko jenuh beli")
        return {"ticker":symbol,"name":name,"region":region,"close":price,"ret1":ret1,"ret5":ret5,
                "ret20":ret20,"rsi":float(strength.iloc[-1]),"vol_ratio":vr,"score":score,
                "date":frame.index[-1].strftime("%Y-%m-%d"),"reasons":reasons}
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError): return None

def scan_stocks():
    universe=load_stock_universe(); data=download_history([x[0] for x in universe])
    ranked=[r for t,n,region in universe if (r:=score_stock(t,n,extract_symbol(data,t),region))]
    ranked.sort(key=lambda r:(r["score"],r["vol_ratio"],abs(r["ret1"]),r["ret5"]),reverse=True)
    if not ranked: raise RuntimeError("Tidak ada data saham valid dari penyedia.")
    now=datetime.now(JAKARTA); latest=max(r["date"] for r in ranked)
    if (now.date()-datetime.strptime(latest,"%Y-%m-%d").date()).days>5:
        raise RuntimeError(f"Data saham terakhir {latest} terlalu lama; laporan dibatalkan.")
    lines=["📊 MARC DAILY SCANNER",
           "━━━━━━━━━━━━━━━━━━━━",
           "PASAR SAHAM | INDONESIA & GLOBAL",
           f"⏱ Analisis dibuat: {now:%d %b %Y • %H:%M WIB}",
           f"🗓 Data terakhir tersedia: {latest}",
           "🎯 Tujuan: shortlist kandidat untuk sesi berikutnya.",
           "ℹ️ Peringkat hanya dari watchlist MARC, bukan seluruh bursa.",
           "",
           "CARA BACA",
           "Skor = gabungan tren, momentum, volume, RSI, dan volatilitas.",
           "Vol 1.0x = setara rata-rata; di atas 1.0x = volume relatif meningkat.",
           "",
           "TOP 10 KANDIDAT",
           "────────────────────"]
    for i,r in enumerate(ranked[:TOP_N],1):
        price=f"Rp{r['close']:,.0f}" if r["ticker"].endswith(".JK") else f"{r['close']:,.2f} (mata uang listing)"
        lines += [f"{i:02d} | {r['ticker']} — {r['region']}",
                  f"   Harga: {price} | Skor: {r['score']} (indikatif)",
                  f"   Perubahan: 1 hari {r['ret1']:+.2f}% • 5 hari {r['ret5']:+.2f}% • 20 hari {r['ret20']:+.2f}%",
                  f"   RSI: {r['rsi']:.0f} | Volume relatif: {r['vol_ratio']:.1f}x",
                  "   Alasan masuk daftar: "+("; ".join(r["reasons"][:3]) if r["reasons"] else "belum ada konfirmasi kuat"),
                  ""]
    lines += ["────────────────────",
               "PANDUAN TINDAKAN",
               "• Gunakan daftar ini sebagai watchlist, bukan instruksi beli.",
               "• Prioritaskan konfirmasi harga, volume, likuiditas, dan berita.",
               "• Cek kalender bursa dan harga broker sebelum transaksi.",
               "• Skor bukan probabilitas keuntungan dan tidak menjamin hasil."]
    return "\n".join(lines)

def scan_crypto():
    universe=load_market_csv(CRYPTO_FILE); data=download_history([x[0] for x in universe],"10d","1h"); ranked=[]
    for ticker,name in universe:
        try:
            f=extract_symbol(data,ticker)
            if not {"Close","Volume"}.issubset(f.columns): continue
            f=f[["Close","Volume"]].dropna()
            if len(f)<25: continue
            c,v=f.Close.astype(float),f.Volume.astype(float); p=float(c.iloc[-1])
            r1=(p/float(c.iloc[max(0,len(c)-25)])-1)*100
            r7=(p/float(c.iloc[max(0,len(c)-169)])-1)*100
            recent_vol=float(v.iloc[-24:].mean()); baseline=float(v.iloc[:-24].mean()) if len(v)>24 else 0
            vr=float(recent_vol/baseline) if baseline>0 else 0
            strength=float(rsi(c).iloc[-1])
            score=max(-5,min(5,r1))*.8+max(-5,min(5,r7))*.5+min(vr,5)*1.5
            if strength>82: score-=2
            if abs(r1)>15: score-=1
            ranked.append({"ticker":ticker,"name":name,"price":p,"ret1":r1,"ret7":r7,"vol":vr,"rsi":strength,"score":score,"date":f.index[-1].strftime("%Y-%m-%d")})
        except (KeyError,ValueError,TypeError,IndexError,ZeroDivisionError): continue
    ranked.sort(key=lambda r:(r["score"],r["vol"]),reverse=True)
    if not ranked: raise RuntimeError("Tidak ada data crypto valid dari penyedia.")
    now=datetime.now(JAKARTA); lines=["📊 MARC DAILY SCANNER",
       "━━━━━━━━━━━━━━━━━━━━",
       "PASAR CRYPTO | MOMENTUM & AKTIVITAS",
       f"⏱ Analisis dibuat: {now:%d %b %Y • %H:%M WIB}",
       f"🗓 Tanggal candle terbaru: {max(r['date'] for r in ranked)}",
       "🎯 Tujuan: menemukan aset dengan momentum dan aktivitas relatif tinggi.",
       "ℹ️ Peringkat hanya dari watchlist MARC; skor hype bukan probabilitas profit.",
       "",
       "CARA BACA",
       "24 jam = perubahan kira-kira 24 candle 1 jam; 7 hari = sekitar 7 hari.",
       "Vol 1.0x = rata-rata volume; lebih tinggi menunjukkan aktivitas relatif naik.",
       "",
       "TOP 10 KANDIDAT",
       "────────────────────"]
    for i,r in enumerate(ranked[:TOP_N],1):
        lines += [f"{i:02d} | {r['ticker']} — {r['name']}",
                  f"   Harga referensi: {r['price']:.6g} USD | Skor momentum: {r['score']:.1f}",
                  f"   Perubahan: 24 jam {r['ret1']:+.2f}% • 7 hari {r['ret7']:+.2f}%",
                  f"   RSI: {r['rsi']:.0f} | Volume relatif: {r['vol']:.1f}x",
                  "   Catatan: periksa pasangan trading, spread, dan kedalaman order book.",
                  ""]
    lines += ["────────────────────",
              "PANDUAN TINDAKAN",
              "• Pergerakan tajam dapat berbalik cepat; hindari mengejar candle.",
              "• Validasi pair/exchange, spread, kedalaman order book, funding, dan berita.",
              "• RSI tinggi dapat menandakan kondisi terlalu panas, bukan sinyal jual otomatis.",
              "• Skor tidak memperhitungkan semua risiko dan bukan jaminan profit."]
    return "\n".join(lines)

def scan_commodities():
    now=datetime.now(JAKARTA); lines=["📊 MARC DAILY SCANNER",
        "━━━━━━━━━━━━━━━━━━━━",
        "PASAR KOMODITAS | SETUP INTRADAY 1–5 JAM",
        f"⏱ Analisis dibuat: {now:%d %b %Y • %H:%M WIB}",
        "🕯 Kerangka analisis: candle 15 menit",
        "ℹ️ Level dihitung dari 20 candle terbaru; indikatif dan dapat berubah.",
        "",
        "CARA BACA",
        "Support = area pantulan potensial • Resistance = area hambatan potensial.",
        "LONG/SHORT WATCH = skenario untuk dipantau, bukan perintah entry.",
        "WAIT = kondisi belum cukup jelas menurut aturan scanner.",
        "",
        "HASIL PER INSTRUMEN",
        "────────────────────"]
    valid=0
    for ticker,name in load_market_csv(COMMODITY_FILE):
        try:
            f=yf.Ticker(ticker).history(period="5d",interval="15m",auto_adjust=True)
            if f is None or f.empty or not {"Close","High","Low"}.issubset(f.columns): continue
            f=f[["Close","High","Low"]].dropna()
            if len(f)<20: continue
            c=f.Close.astype(float); recent=f.iloc[-20:]; p=float(c.iloc[-1])
            s=float(recent.Low.min()); resistance=float(recent.High.max())
            ema9=float(c.ewm(span=9,adjust=False).mean().iloc[-1]); ema21=float(c.ewm(span=21,adjust=False).mean().iloc[-1])
            strength=float(rsi(c).iloc[-1]); span=max(resistance-s,1e-9)
            if ema9>ema21 and 45<=strength<72 and p<resistance*.997:
                bias="LONG WATCH" if p<s+span*.35 else "tunggu konfirmasi"
            elif ema9<ema21 and 28<strength<=55 and p>s*1.003:
                bias="SHORT WATCH" if p>resistance-span*.65 else "tunggu konfirmasi"
            else: bias="WAIT / no-trade"
            lines += [f"INSTRUMEN: {ticker} — {name}",
                      f"   Harga referensi: {p:.4g}",
                      f"   Support indikatif: {s:.4g} | Jarak harga ke support: {max((p-s)/p*100,0):.2f}%",
                      f"   Resistance indikatif: {resistance:.4g} | Jarak harga ke resistance: {max((resistance-p)/p*100,0):.2f}%",
                      f"   Tren: EMA9 {'di atas' if ema9>ema21 else 'di bawah/bersilangan dengan'} EMA21 | RSI: {strength:.0f}",
                      f"   STATUS: {bias}",
                      ""]
            valid+=1
        except Exception as exc: print(f"Commodity skip {ticker}: {exc}",file=sys.stderr)
    if not valid: raise RuntimeError("Data intraday komoditas tidak tersedia.")
    lines += ["────────────────────",
              "CHECKLIST SEBELUM TRADING",
              "• Pastikan sesi perdagangan aktif dan data harga masih relevan.",
              "• Cek spread, likuiditas, kontrak futures, dan risiko rollover.",
              "• Tentukan entry, invalidasi skenario, stop-loss, dan ukuran posisi terlebih dahulu.",
              "• Jika level terlalu dekat atau arah belum jelas, prioritaskan WAIT.",
              "• Analisis teknikal tidak menjamin hasil; validasi melalui platform broker."]
    return "\n".join(lines)

def send_telegram(message):
    token=os.environ.get("TELEGRAM_BOT_TOKEN","").strip(); chat=os.environ.get("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat: raise RuntimeError("Secret TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID belum dikonfigurasi.")
    chunks=[]; current=""
    for line in message.splitlines():
        if len(current)+len(line)+1>3500:
            if current: chunks.append(current)
            current=line
        else: current=f"{current}\n{line}" if current else line
    if current: chunks.append(current)
    for chunk in chunks:
        response=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id":chat,"text":chunk,"disable_web_page_preview":True},timeout=25)
        response.raise_for_status()
        if not response.json().get("ok"): raise RuntimeError("Telegram API gagal mengirim laporan.")

def main():
    mode=os.environ.get("MARC_REPORT_TYPE","all").strip().lower(); reports=[]
    tasks=[]
    if mode in ("all","stocks"): tasks.append(("saham",scan_stocks))
    if mode in ("all","evening","crypto","crypto_commodities"): tasks.append(("crypto",scan_crypto))
    if mode in ("all","evening","commodities","crypto_commodities"): tasks.append(("komoditas",scan_commodities))
    if not tasks: raise RuntimeError(f"MARC_REPORT_TYPE tidak dikenal: {mode}")
    for name,func in tasks:
        try: reports.append(func())
        except Exception as exc:
            if mode in ("stocks","crypto","commodities"): raise
            reports.append(f"⚠️ Laporan {name} gagal: {exc}")
    message="\n\n━━━━━━━━━━━━━━━━━━\n\n".join(reports); send_telegram(message); print(message)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(f"MARC ERROR: {exc}",file=sys.stderr); raise
