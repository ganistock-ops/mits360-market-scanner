from flask import Flask, jsonify
from flask_cors import CORS
from SmartApi import SmartConnect
import pyotp
import os
import pytz
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)
IST = pytz.timezone('Asia/Kolkata')

API_KEY = os.environ.get("ANGEL_API_KEY", "")
CLIENT_ID = os.environ.get("ANGEL_CLIENT_ID", "")
MPIN = os.environ.get("ANGEL_MPIN", "")
TOTP_SECRET = os.environ.get("ANGEL_TOTP_SECRET", "")

# Nifty 50 F&O stocks with tokens
FNO_STOCKS = {
    "NIFTY": "26000", "BANKNIFTY": "26009",
    "RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333",
    "ICICIBANK": "4963", "INFY": "1594", "ITC": "1660",
    "SBIN": "3045", "BHARTIARTL": "10604", "KOTAKBANK": "1922",
    "LT": "11483", "AXISBANK": "5900", "BAJFINANCE": "317",
    "MARUTI": "10999", "TITAN": "3506", "SUNPHARMA": "3351",
    "WIPRO": "3787", "TATAMOTORS": "3456", "TATASTEEL": "3408",
    "JSWSTEEL": "11723", "HINDALCO": "1363", "ONGC": "2475",
    "NTPC": "11630", "POWERGRID": "14977", "ADANIENT": "25",
    "ADANIPORTS": "15083", "HCLTECH": "7229", "TECHM": "13538",
    "DRREDDY": "881", "CIPLA": "694"
}

def get_session():
    try:
        obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(CLIENT_ID, MPIN, totp)
        if data and data.get("status"):
            return obj, data["data"]["jwtToken"]
    except Exception as e:
        print(f"Login error: {e}")
    return None, None

def get_option_chain(obj, jwt_token, symbol, expiry):
    """Fetch option chain for a symbol"""
    try:
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": API_KEY
        }
        payload = {
            "name": symbol,
            "expirydate": expiry
        }
        r = requests.post(
            "https://apiconnect.angelbroking.com/rest/secure/angelbroking/marketData/v1/putCallRatio",
            json=payload,
            headers=headers,
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Option chain error: {e}")
    return None

def get_oi_buildup(obj, jwt_token):
    """Fetch OI buildup data"""
    try:
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": API_KEY
        }
        # OI gainers
        r = requests.get(
            "https://apiconnect.angelbroking.com/rest/secure/angelbroking/marketData/v1/OIdata",
            headers=headers,
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"OI buildup error: {e}")
    return None

@app.route('/api/oi-scanner', methods=['GET'])
def oi_scanner():
    try:
        now = datetime.now(IST)
        obj, jwt_token = get_session()
        if not obj:
            return jsonify({"status": "error", "message": "Angel One login failed."}), 500

        # Fetch market data for F&O stocks to calculate OI change
        tokens = list(FNO_STOCKS.values())[:20]
        exchange_tokens = {"NFO": tokens, "NSE": tokens}

        # Get quotes with OI data
        quote_data = obj.getMarketData("FULL", {"NSE": list(FNO_STOCKS.values())[2:]})

        oi_buildup = []
        long_buildup = []   # Price up + OI up
        short_buildup = []  # Price down + OI up
        long_unwinding = [] # Price down + OI down
        short_covering = [] # Price up + OI down

        if quote_data and quote_data.get("status"):
            fetched = quote_data.get("data", {}).get("fetched", [])
            sym_map = {v: k for k, v in FNO_STOCKS.items()}

            for item in fetched:
                try:
                    token = str(item.get("symbolToken", ""))
                    sym = sym_map.get(token, token)
                    ltp = float(item.get("ltp", 0))
                    close = float(item.get("close", ltp))
                    oi = int(item.get("openInterest", 0))
                    oi_change = float(item.get("openInterestChange", 0))
                    vol = int(item.get("tradedVolume", 0))

                    change_pct = ((ltp - close) / close * 100) if close > 0 else 0
                    oi_change_pct = (oi_change / (oi - oi_change) * 100) if (oi - oi_change) > 0 else 0

                    stock = {
                        "symbol": sym,
                        "price": round(ltp, 2),
                        "change_pct": round(change_pct, 2),
                        "oi": oi,
                        "oi_change": int(oi_change),
                        "oi_change_pct": round(oi_change_pct, 2),
                        "volume": vol,
                        "interpretation": ""
                    }

                    # OI Buildup Classification
                    if change_pct > 0 and oi_change > 0:
                        stock["interpretation"] = "LONG BUILDUP"
                        stock["signal"] = "bullish"
                        long_buildup.append(stock)
                    elif change_pct < 0 and oi_change > 0:
                        stock["interpretation"] = "SHORT BUILDUP"
                        stock["signal"] = "bearish"
                        short_buildup.append(stock)
                    elif change_pct < 0 and oi_change < 0:
                        stock["interpretation"] = "LONG UNWINDING"
                        stock["signal"] = "bearish"
                        long_unwinding.append(stock)
                    elif change_pct > 0 and oi_change < 0:
                        stock["interpretation"] = "SHORT COVERING"
                        stock["signal"] = "bullish"
                        short_covering.append(stock)

                except Exception as e:
                    print(f"Item error: {e}")
                    continue

        # Sort by OI change %
        long_buildup = sorted(long_buildup, key=lambda x: x['oi_change_pct'], reverse=True)[:10]
        short_buildup = sorted(short_buildup, key=lambda x: x['oi_change_pct'], reverse=True)[:10]
        long_unwinding = sorted(long_unwinding, key=lambda x: x['oi_change_pct'])[:10]
        short_covering = sorted(short_covering, key=lambda x: x['oi_change_pct'], reverse=True)[:10]

        # PCR for Nifty (using available data)
        pcr_data = []
        try:
            pcr_raw = get_option_chain(obj, jwt_token, "NIFTY", "")
            if pcr_raw and pcr_raw.get("status"):
                pcr_items = pcr_raw.get("data", [])
                for item in pcr_items[:15]:
                    try:
                        strike = item.get("strikePrice", 0)
                        call_oi = int(item.get("CE", {}).get("openInterest", 0))
                        put_oi = int(item.get("PE", {}).get("openInterest", 0))
                        pcr = round(put_oi / call_oi, 2) if call_oi > 0 else 0
                        pcr_data.append({
                            "strike": strike,
                            "call_oi": call_oi,
                            "put_oi": put_oi,
                            "pcr": pcr
                        })
                    except:
                        continue
        except Exception as e:
            print(f"PCR error: {e}")

        # Overall PCR
        total_call_oi = sum(p["call_oi"] for p in pcr_data)
        total_put_oi = sum(p["put_oi"] for p in pcr_data)
        overall_pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0

        pcr_signal = "NEUTRAL"
        if overall_pcr > 1.2:
            pcr_signal = "BULLISH"
        elif overall_pcr < 0.8:
            pcr_signal = "BEARISH"

        return jsonify({
            "status": "success",
            "timestamp": now.strftime("%d %b %Y, %I:%M %p IST"),
            "long_buildup": long_buildup,
            "short_buildup": short_buildup,
            "long_unwinding": long_unwinding,
            "short_covering": short_covering,
            "pcr": {
                "overall": overall_pcr,
                "signal": pcr_signal,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "strikes": pcr_data[:10]
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/scanner', methods=['GET'])
def scanner():
    try:
        now = datetime.now(IST)
        obj, jwt_token = get_session()
        if not obj:
            return jsonify({"status": "error", "message": "Angel One login failed."}), 500

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

        quote_data = obj.getMarketData("FULL", {"NSE": list(token_map.values())})
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
                    change_pct = ((ltp - close) / close * 100) if close > 0 else 0
                    stocks.append({
                        "symbol": sym, "price": round(ltp, 2),
                        "change_pct": round(change_pct, 2), "volume": vol,
                        "vol_ratio": 1.0, "week52_high": round(high52, 2),
                        "week52_low": round(low52, 2),
                        "near_52w_high": ltp >= high52 * 0.97 if high52 > 0 else False,
                        "near_52w_low": ltp <= low52 * 1.03 if low52 > 0 else False,
                    })
                except: continue

        return jsonify({
            "status": "success",
            "timestamp": now.strftime("%d %b %Y, %I:%M %p IST"),
            "gainers": sorted([s for s in stocks if s['change_pct'] > 0], key=lambda x: x['change_pct'], reverse=True)[:10],
            "losers": sorted([s for s in stocks if s['change_pct'] < 0], key=lambda x: x['change_pct'])[:10],
            "high52": sorted([s for s in stocks if s['near_52w_high']], key=lambda x: x['change_pct'], reverse=True)[:10],
            "low52": sorted([s for s in stocks if s['near_52w_low']], key=lambda x: x['change_pct'])[:10],
            "vol_shocker": sorted(stocks, key=lambda x: x['vol_ratio'], reverse=True)[:10]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "MITS 360 Scanner API"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
