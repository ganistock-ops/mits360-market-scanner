from flask import Flask, jsonify
from flask_cors import CORS
from SmartApi import SmartConnect
import pyotp
import os
import pytz
from datetime import datetime

app = Flask(__name__)
CORS(app)
IST = pytz.timezone('Asia/Kolkata')

API_KEY = os.environ.get("ANGEL_API_KEY", "")
CLIENT_ID = os.environ.get("ANGEL_CLIENT_ID", "")
MPIN = os.environ.get("ANGEL_MPIN", "")
TOTP_SECRET = os.environ.get("ANGEL_TOTP_SECRET", "")

def get_angel_session():
    try:
        obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(CLIENT_ID, MPIN, totp)
        if data["status"]:
            return obj
    except Exception as e:
        print(f"Angel login error: {e}")
    return None

def parse_gainers_losers(data, key="gainers"):
    try:
        items = data.get("data", {}).get(key, [])
        result = []
        for item in items[:10]:
            result.append({
                "symbol": item.get("tradingSymbol", "").replace("-EQ",""),
                "price": round(float(item.get("ltp", 0)), 2),
                "change_pct": round(float(item.get("percentChange", 0)), 2),
                "volume": int(item.get("tradedVolume", 0))
            })
        return result
    except:
        return []

@app.route('/api/scanner', methods=['GET'])
def scanner():
    try:
        now = datetime.now(IST)
        obj = get_angel_session()
        if not obj:
            return jsonify({"status": "error", "message": "Angel One login failed. Check credentials."}), 500

        # Top Gainers & Losers — NSE Cash
        gainers_raw = obj.gainersLosers({"expiryType": "NEAR", "dataType": "PercOIGainers", "expiryType": "NEAR"})
        
        # Use NSE market data
        gainers = []
        losers = []
        high52 = []
        low52 = []
        vol_shocker = []

        # Fetch Nifty 50 quotes for gainers/losers
        nifty50 = [
            "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","ITC","SBIN",
            "BHARTIARTL","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
            "TITAN","SUNPHARMA","WIPRO","ONGC","NTPC","ULTRACEMCO","POWERGRID",
            "BAJFINANCE","HCLTECH","JSWSTEEL","TATASTEEL","ADANIENT","ADANIPORTS",
            "COALINDIA","NESTLEIND","TECHM","DIVISLAB","DRREDDY","CIPLA","GRASIM",
            "HINDALCO","INDUSINDBK","BPCL","TATACONSUM","BAJAJFINSV","EICHERMOT",
            "HEROMOTOCO","BRITANNIA","TATAMOTORS","M&M","SBILIFE","HDFCLIFE",
            "SHREECEM","BAJAJ-AUTO","TRENT","APOLLOHOSP","DMART"
        ]

        stocks = []
        for sym in nifty50:
            try:
                ltp_data = obj.ltpData("NSE", sym+"-EQ", "")
                if ltp_data and ltp_data.get("status"):
                    d = ltp_data["data"]
                    price = float(d.get("ltp", 0))
                    close = float(d.get("close", price))
                    change_pct = ((price - close) / close * 100) if close > 0 else 0
                    stocks.append({
                        "symbol": sym,
                        "price": round(price, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": 0,
                        "vol_ratio": 1.0,
                        "week52_high": round(float(d.get("high", price)), 2),
                        "week52_low": round(float(d.get("low", price)), 2),
                    })
            except:
                continue

        gainers = sorted([s for s in stocks if s['change_pct'] > 0], key=lambda x: x['change_pct'], reverse=True)[:10]
        losers = sorted([s for s in stocks if s['change_pct'] < 0], key=lambda x: x['change_pct'])[:10]
        high52 = sorted(stocks, key=lambda x: x['week52_high'], reverse=True)[:10]
        low52 = sorted(stocks, key=lambda x: x['week52_low'])[:10]
        vol_shocker = stocks[:10]

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
    return jsonify({"status": "ok", "service": "MITS 360 Scanner API - Angel One"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
