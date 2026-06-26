from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import pytz
import threading
import time

app = Flask(__name__)
CORS(app)

IST = pytz.timezone('Asia/Kolkata')

# Cache
cache = {"data": None, "timestamp": None}
cache_lock = threading.Lock()

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/live-equity-market",
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except:
        pass
    return session

def fetch_nse_data(session, url):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def fetch_data():
    try:
        session = get_nse_session()
        now = datetime.now(IST)

        # Top Gainers
        gainers_raw = fetch_nse_data(session, "https://www.nseindia.com/api/live-analysis-variations?index=gainers")
        # Top Losers  
        losers_raw = fetch_nse_data(session, "https://www.nseindia.com/api/live-analysis-variations?index=loosers")
        # 52W High
        high52_raw = fetch_nse_data(session, "https://www.nseindia.com/api/live-analysis-variations?index=high52")
        # 52W Low
        low52_raw = fetch_nse_data(session, "https://www.nseindia.com/api/live-analysis-variations?index=low52")
        # Volume Shockers
        vol_raw = fetch_nse_data(session, "https://www.nseindia.com/api/live-analysis-volume-shockers")

        def parse_gainers_losers(raw):
            if not raw:
                return []
            data = raw.get("NIFTY", {}).get("data", []) or raw.get("data", [])
            result = []
            for item in data[:10]:
                try:
                    result.append({
                        "symbol": item.get("symbol", ""),
                        "price": round(float(item.get("ltp", 0)), 2),
                        "change_pct": round(float(item.get("perChange", 0)), 2),
                        "volume": int(item.get("tradedQuantity", 0))
                    })
                except:
                    continue
            return result

        def parse_52w(raw):
            if not raw:
                return []
            data = raw.get("data", [])
            result = []
            for item in data[:10]:
                try:
                    result.append({
                        "symbol": item.get("symbol", ""),
                        "price": round(float(item.get("ltp", 0)), 2),
                        "change_pct": round(float(item.get("perChange", 0)), 2),
                        "week52_high": round(float(item.get("52wH", 0)), 2),
                        "week52_low": round(float(item.get("52wL", 0)), 2),
                    })
                except:
                    continue
            return result

        def parse_vol(raw):
            if not raw:
                return []
            data = raw.get("data", [])
            result = []
            for item in data[:10]:
                try:
                    result.append({
                        "symbol": item.get("symbol", ""),
                        "price": round(float(item.get("ltp", 0)), 2),
                        "change_pct": round(float(item.get("perChange", 0)), 2),
                        "vol_ratio": round(float(item.get("ratio", 1)), 2),
                        "volume": int(item.get("totalTradedVolume", 0))
                    })
                except:
                    continue
            return result

        gainers = parse_gainers_losers(gainers_raw)
        losers = parse_gainers_losers(losers_raw)
        high52 = parse_52w(high52_raw)
        low52 = parse_52w(low52_raw)
        vol_shocker = parse_vol(vol_raw)

        # Only cache if we got some data
        if gainers or losers or high52 or vol_shocker:
            result = {
                "status": "success",
                "timestamp": now.strftime("%d %b %Y, %I:%M %p IST"),
                "gainers": gainers,
                "losers": losers,
                "high52": high52,
                "low52": low52,
                "vol_shocker": vol_shocker
            }
            with cache_lock:
                cache["data"] = result
                cache["timestamp"] = time.time()
            print(f"Cache updated: {len(gainers)} gainers, {len(losers)} losers")
        else:
            print("No data received from NSE")

    except Exception as e:
        print(f"Fetch error: {e}")

def background_refresh():
    while True:
        fetch_data()
        time.sleep(300)

# Start background thread
t = threading.Thread(target=background_refresh, daemon=True)
t.start()

@app.route('/api/scanner', methods=['GET'])
def scanner():
    with cache_lock:
        data = cache["data"]

    if data:
        return jsonify(data)

    # First request — try fetching directly
    fetch_data()
    with cache_lock:
        data = cache["data"]
    if data:
        return jsonify(data)

    return jsonify({
        "status": "error",
        "message": "NSE data unavailable. Market may be closed. Try again."
    }), 503

@app.route('/health', methods=['GET'])
def health():
    with cache_lock:
        cached = cache["timestamp"] is not None
    return jsonify({"status": "ok", "service": "MITS 360 Scanner API", "cached": cached})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
