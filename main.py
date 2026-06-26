from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
CORS(app)

# NSE 200 stocks list (Nifty 200 universe)
NIFTY200_SYMBOLS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
    "SUNPHARMA.NS","WIPRO.NS","ONGC.NS","NTPC.NS","ULTRACEMCO.NS",
    "POWERGRID.NS","BAJFINANCE.NS","HCLTECH.NS","JSWSTEEL.NS","TATASTEEL.NS",
    "ADANIENT.NS","ADANIPORTS.NS","COALINDIA.NS","NESTLEIND.NS","TECHM.NS",
    "DIVISLAB.NS","DRREDDY.NS","CIPLA.NS","GRASIM.NS","HINDALCO.NS",
    "INDUSINDBK.NS","BPCL.NS","TATACONSUM.NS","BAJAJFINSV.NS","APOLLOHOSP.NS",
    "EICHERMOT.NS","HEROMOTOCO.NS","BRITANNIA.NS","TATAMOTORS.NS","M&M.NS",
    "SBILIFE.NS","HDFCLIFE.NS","UPL.NS","SHREECEM.NS","BAJAJ-AUTO.NS",
    "PIDILITIND.NS","SIEMENS.NS","HAVELLS.NS","BERGEPAINT.NS","MARICO.NS",
    "DABUR.NS","GODREJCP.NS","MCDOWELL-N.NS","LUPIN.NS","TORNTPHARM.NS",
    "AMBUJACEM.NS","ACC.NS","SAIL.NS","NMDC.NS","VEDL.NS",
    "GAIL.NS","IOC.NS","HPCL.NS","MOTHERSON.NS","BOSCHLTD.NS",
    "CUMMINSIND.NS","MUTHOOTFIN.NS","CHOLAFIN.NS","PFC.NS","RECLTD.NS",
    "CONCOR.NS","VOLTAS.NS","TRENT.NS","DMART.NS","NAUKRI.NS",
    "INDIAMART.NS","PERSISTENT.NS","COFORGE.NS","LTIM.NS","MPHASIS.NS",
    "OFSS.NS","HDFCAMC.NS","ICICIPRULI.NS","ICICIGI.NS","SBICARD.NS",
    "BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS","RBLBANK.NS","PNB.NS",
    "BANKBARODA.NS","CANBK.NS","UNIONBANK.NS","CENTRALBNK.NS","INDIANB.NS",
    "AUROPHARMA.NS","BIOCON.NS","ALKEM.NS","IPCA.NS","ABBOTINDIA.NS",
    "METROPOLIS.NS","LALPATHLAB.NS","FORTIS.NS","MAXHEALTH.NS","NHPC.NS",
    "TATAPOWER.NS","ADANIGREEN.NS","TORNTPOWER.NS","CESC.NS","JSWENERGY.NS",
    "JINDALSTEL.NS","RATNAMANI.NS","WELCORP.NS","KALYANKJIL.NS","SENCO.NS",
    "PAGEIND.NS","RELAXO.NS","BATA.NS","VBL.NS","RADICO.NS",
    "UBL.NS","COLPAL.NS","EMAMILTD.NS","JYOTHYLAB.NS","VSTIND.NS",
    "ZOMATO.NS","NYKAA.NS","PAYTM.NS","POLICYBZR.NS","CARTRADE.NS",
    "IRCTC.NS","RVNL.NS","IRFC.NS","HUDCO.NS","RAILVIKAS.NS",
    "OBEROIRLTY.NS","DLF.NS","GODREJPROP.NS","PRESTIGE.NS","BRIGADE.NS",
    "PHOENIXLTD.NS","SOBHA.NS","SUNTV.NS","ZEEL.NS","PVRINOX.NS",
    "INOXWIND.NS","SUZLON.NS","GRENINFRA.NS","KPIGREEN.NS","WAAREEENER.NS",
    "TATACHEM.NS","PIDILITIND.NS","SRF.NS","AARTIIND.NS","DEEPAKNITR.NS",
    "GNFC.NS","GSFC.NS","CHAMBALFERT.NS","COROMANDEL.NS","PIIND.NS",
    "ASTRAL.NS","SUPREMEIND.NS","POLYMED.NS","LXCHEM.NS","ANURAS.NS",
    "KPITTECH.NS","LTTS.NS","TATAELXSI.NS","ZENSAR.NS","NIITLTD.NS",
    "APLAPOLLO.NS","JINDALPOLY.NS","JINDALSAW.NS","MANAPPURAM.NS","IIFL.NS",
    "ANGELONE.NS","5PAISA.NS","MOTILALOFS.NS","NUVAMA.NS","EDELWEISS.NS",
    "GESHIP.NS","SCI.NS","ADANIPORTS.NS","ADANIENT.NS","TRIVENI.NS",
    "TRITURBINE.NS","BHEL.NS","BEL.NS","HAL.NS","COCHINSHIP.NS",
    "MAZAGON.NS","GRSE.NS","MIDHANI.NS","MTAR.NS","DATAPATTERNSN.NS"
]

IST = pytz.timezone('Asia/Kolkata')

def get_market_data():
    """Fetch data for all symbols using yfinance"""
    try:
        symbols_str = " ".join(NIFTY200_SYMBOLS[:100])  # batch 100 at a time
        data = yf.download(
            tickers=symbols_str,
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )
        return data
    except Exception as e:
        return None

def get_52week_data():
    """Fetch 1 year data for 52W high/low"""
    try:
        symbols_str = " ".join(NIFTY200_SYMBOLS[:100])
        data = yf.download(
            tickers=symbols_str,
            period="52wk",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )
        return data
    except Exception as e:
        return None

def parse_stocks(data, symbols):
    """Parse downloaded data into list of stock dicts"""
    stocks = []
    for sym in symbols:
        try:
            if len(symbols) == 1:
                df = data
            else:
                df = data[sym] if sym in data.columns.get_level_values(0) else None

            if df is None or df.empty or len(df) < 2:
                continue

            df = df.dropna()
            if len(df) < 2:
                continue

            prev_close = float(df['Close'].iloc[-2])
            curr_close = float(df['Close'].iloc[-1])
            curr_volume = float(df['Volume'].iloc[-1])
            prev_volume = float(df['Volume'].iloc[-2])

            if prev_close <= 0:
                continue

            change_pct = ((curr_close - prev_close) / prev_close) * 100
            vol_ratio = curr_volume / prev_volume if prev_volume > 0 else 1

            name = sym.replace(".NS", "")
            stocks.append({
                "symbol": name,
                "price": round(curr_close, 2),
                "change_pct": round(change_pct, 2),
                "volume": int(curr_volume),
                "vol_ratio": round(vol_ratio, 2)
            })
        except Exception:
            continue
    return stocks

@app.route('/api/scanner', methods=['GET'])
def scanner():
    try:
        now = datetime.now(IST)
        
        # Fetch 2-day data
        data_2d = yf.download(
            tickers=" ".join(NIFTY200_SYMBOLS[:80]),
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )

        # Fetch 52-week data
        data_52w = yf.download(
            tickers=" ".join(NIFTY200_SYMBOLS[:80]),
            period="52wk",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True
        )

        stocks = []
        for sym in NIFTY200_SYMBOLS[:80]:
            try:
                df_2d = data_2d[sym].dropna() if sym in data_2d.columns.get_level_values(0) else None
                df_52 = data_52w[sym].dropna() if sym in data_52w.columns.get_level_values(0) else None

                if df_2d is None or len(df_2d) < 2:
                    continue

                prev_close = float(df_2d['Close'].iloc[-2])
                curr_close = float(df_2d['Close'].iloc[-1])
                curr_vol = float(df_2d['Volume'].iloc[-1])
                prev_vol = float(df_2d['Volume'].iloc[-2])

                if prev_close <= 0:
                    continue

                change_pct = ((curr_close - prev_close) / prev_close) * 100
                vol_ratio = round(curr_vol / prev_vol, 2) if prev_vol > 0 else 1.0

                week52_high = float(df_52['High'].max()) if df_52 is not None and not df_52.empty else None
                week52_low = float(df_52['Low'].min()) if df_52 is not None and not df_52.empty else None

                near_52w_high = week52_high and curr_close >= week52_high * 0.97
                near_52w_low = week52_low and curr_close <= week52_low * 1.03

                stocks.append({
                    "symbol": sym.replace(".NS", ""),
                    "price": round(curr_close, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": int(curr_vol),
                    "vol_ratio": vol_ratio,
                    "week52_high": round(week52_high, 2) if week52_high else None,
                    "week52_low": round(week52_low, 2) if week52_low else None,
                    "near_52w_high": near_52w_high,
                    "near_52w_low": near_52w_low
                })
            except Exception:
                continue

        # Sort lists
        gainers = sorted([s for s in stocks if s['change_pct'] > 0], key=lambda x: x['change_pct'], reverse=True)[:10]
        losers = sorted([s for s in stocks if s['change_pct'] < 0], key=lambda x: x['change_pct'])[:10]
        high52 = [s for s in stocks if s['near_52w_high']]
        high52 = sorted(high52, key=lambda x: x['change_pct'], reverse=True)[:10]
        low52 = [s for s in stocks if s['near_52w_low']]
        low52 = sorted(low52, key=lambda x: x['change_pct'])[:10]
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
