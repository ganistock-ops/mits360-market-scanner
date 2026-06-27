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

NIFTY50 = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","ITC","SBIN",
    "BHARTIARTL","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
    "TITAN","SUNPHARMA","WIPRO","ONGC","NTPC","ULTRACEMCO","POWERGRID",
    "BAJFINANCE","HCLTECH","JSWSTEEL","TATASTEEL","ADANIENT","ADANIPORTS",
    "COALINDIA","NESTLEIND","TECHM","DIVISLAB","DRREDDY","CIPLA","GRASIM",
    "HINDALCO","INDUSINDBK","BPCL","TATACONSUM","BAJAJFINSV","EICHERMOT",
    "HEROMOTOCO","BRITANNIA","TATAMOTORS","M&M","SBILIFE","HDFCLIFE",
    "SHREECEM","BAJAJ-AUTO","TRENT","APOLLOHOSP","DMART"
]

def get_session():
    try:
        obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(CLIENT_ID, MPIN, totp)
        if data and data.get("status"):
            return obj
    except Exception as e:
        print(f"Login error: {e}")
    return None

@app.route('/api/scanner', methods=['GET'])
def scanner():
    try:
        now = datetime.now(IST)
        obj = get_session()
        if not obj:
            return jsonify({"status": "error", "message": "Angel One login failed."}), 500

        # Fetch quotes for all Nifty 50 stocks
        token_map = {
            "RELIANCE":"2885","TCS":"11536","HDFCBANK":"1333","ICICIBANK":"4963",
            "INFY":"1594","ITC":"1660","SBIN":"3045","BHARTIARTL":"10604",
            "KOTAKBANK":"1922","LT":"11483","AXISBANK":"5900","ASIANPAINT":"236",
            "MARUTI":"10999","TITAN":"3506","SUNPHARMA":"3351","WIPRO":"3787",
            "ONGC":"2475","NTPC":"11630","ULTRACEMCO":"11532","POWERGRID":"14977",
            "BAJFINANCE":"317","HCLTECH":"7229","JSWSTEEL":"11723","TATASTEEL":"3408",
            "ADANIENT":"25","ADANIPORTS":"15083","COALINDIA":"20374","NESTLEIND":"17963",
            "TECHM":"13538","DIVISLAB":"10940","DRREDDY":"881","CIPLA":"694",
            "GRASIM":"1232","HINDALCO":"1363","INDUSINDBK":"5258","BPCL":"526",
            "TATACONSUM":"3432","BAJAJFINSV":"16675","EICHERMOT":"910","HEROMOTOCO":"1348",
            "BRITANNIA":"547","TATAMOTORS":"3456","M&M":"519","SBILIFE":"21808",
            "HDFCLIFE":"467","SHREECEM":"24349","BAJAJ-AUTO":"16669","TRENT":"1964",
            "APOLLOHOSP":"157","DMART":"19913"
        }

        exchange_tokens = {"NSE": list(token_map.values())}
        
        quote_data = obj.getMarketData("FULL", exchange_tokens)
        
        stocks = []
        if quote_data and quote_data.get("status"):
            fetched = quote_data.get("data", {}).get("fetched", [])
            sym_map = {v: k for k, v in token_map.items()}
            
            for item in fetched:
                try:
                    token = str(item.get("symbolToken", ""))
                    sym = sym_map.get(token, token)
                    ltp = float(item.get("ltp", 0))
                    close = float(item.get("close", ltp))
                    high52 = float(item.get("fiftyTwoWeekHighPrice", ltp))
                    low52 = float(item.get("fiftyTwoWeekLowPrice", ltp))
                    vol = int(item.get("tradedVolume", 0))
                    avg_vol = int(item.get("averageTradedPrice", vol) or vol)
                    change_pct = ((ltp - close) / close * 100) if close > 0 else 0
                    vol_ratio = round(vol / avg_vol, 2) if avg_vol > 0 else 1.0

                    stocks.append({
                        "symbol": sym,
                        "price": round(ltp, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": vol,
                        "vol_ratio": vol_ratio,
                        "week52_high": round(high52, 2),
                        "week52_low": round(low52, 2),
                        "near_52w_high": ltp >= high52 * 0.97 if high52 > 0 else False,
                        "near_52w_low": ltp <= low52 * 1.03 if low52 > 0 else False,
                    })
                except:
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
    return jsonify({"status": "ok", "service": "MITS 360 Scanner API - Angel One"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
