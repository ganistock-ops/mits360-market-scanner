from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# Nifty 50 stocks only (fast & reliable)
STOCKS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
    "SUNPHARMA.NS","WIPRO.NS","ONGC.NS","NTPC.NS","ULTRACEMCO.NS",
    "POWERGRID.NS","BAJFINANCE.NS","HCLTECH.NS","JSWSTEEL.NS","TATASTEEL.NS",
    "ADANIENT.NS","ADANIPORTS.NS","COALINDIA.NS","NESTLEIND.NS","TECHM.NS",
    "DIVISLAB.NS","DRREDDY.NS","CIPLA.NS","GRASIM.NS","HINDALCO.NS",
    "INDUSINDBK.NS","BPCL.NS","TATACONSUM.NS","BAJAJFINSV.NS","APOLLOHOSP.NS",
    "EICHERMOT.NS","HEROMOTOCO.NS","BRITANNIA.NS","TATAMOTORS.NS","M&M.NS",
    "SBILIFE.NS","HDFCLIFE.NS","SHREECEM.NS","BAJAJ-AUTO.NS","TRENT.NS"
]

IST = pytz.timezone('Asia/Kolkata')

@app.route('/api/scanner', methods=['GET'])
def scanner():
    try:
        now = datetime.now(IST)

        # Fetch 2-day data for change %
        tickers_str = " ".join(STOCKS)
        
        data_2d = yf.download(
            tickers=tickers_str,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )

        data_52w = yf.download(
            tickers=tickers_str,
            period="52wk",
            interval="1wk",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )

        stocks = []
        for sym in STOCKS:
            try:
                df = data_2d[sym].dropna() if sym in data_2d.columns.get_level_values(0) else None
                df52 = data_52w[sym].dropna() if sym in data_52w.columns.get_level_values(0) else None

                if df is None or len(df) < 2:
                    continue

                prev_close = float(df['Close'].iloc[-2])
                curr_close = float(df['Close'].iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])
                prev_vol = float(df['Volume'].iloc[-2])

                if prev_close <= 0:
                    continue

                change_pct = ((curr_close - prev_close) / prev_close) * 100
                vol_ratio = round(curr_vol / prev_vol, 2) if prev_vol > 0 else 1.0

                week52_high = float(df52['High'].max()) if df52 is not None and not df52.empty else curr_close
                week52_low = float(df52['Low'].min()) if df52 is not None and not df52.empty else curr_close

                near_52w_high = curr_close >= week52_high * 0.97
                near_52w_low = curr_close <= week52_low * 1.03

                stocks.append({
                    "symbol": sym.replace(".NS", ""),
                    "price": round(curr_close, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": int(curr_vol),
                    "vol_ratio": vol_ratio,
                    "week52_high": round(week52_high, 2),
                    "week52_low": round(week52_low, 2),
                    "near_52w_high": near_52w_high,
                    "near_52w_low": near_52w_low
                })
            except Exception:
                continue

        gainers = sorted([s for s in stocks if s['change_pct'] > 0], key=lambda x: x['change_pct'], reverse=True)[:10]
        losers = sorted([s for s in stocks if s['change_pct'] < 0], key=lambda x: x['change_pct'])[:10]
        high52 = sorted([s for s in stocks if s['near_52w_high']], key=lambda x: x['change_pct'], reverse=True)[:10]
        low52 = sorted([s for s in stocks if s['near_52w_low']], key=lambda x: x['change_pct'])[:10]
        vol_shocker = sorted(stocks, key=lambda x: x['vol_ratio'], reverse=True)[:10]

        return jsonify({
            "status": "success",
            "timestamp": now.strftime("%d %b %Y, %I:%M %p IST"),
            "gainers": gainers,
            "losers": losers,
            "high52": high52,
            "low52": low52,
            "vol_shocker": vol_shocker
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "MITS 360 Scanner API"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
