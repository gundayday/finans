import streamlit as st
import pandas as pd
import json
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import os
from datetime import datetime
import plotly.express as px
import base64
import numpy as np
import google.generativeai as genai  # Hata Giderildi: Import eklendi

# --- AI ANALİZ KURULUMU (GEMINI) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.sidebar.warning("⚠️ Gemini API Key bulunamadı! Lütfen Secrets kısmına ekleyin.")

# --- GITHUB OTOMATIK KAYIT FONKSIYONU ---
def github_a_kaydet(dosya_adi, veri):
    try:
        with open(dosya_adi, "w") as f:
            json.dump(veri, f, indent=2)
        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            url = f"https://api.github.com/repos/{repo}/contents/{dosya_adi}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            r = requests.get(url, headers=headers)
            sha = r.json().get("sha") if r.status_code == 200 else None
            content = base64.b64encode(json.dumps(veri, indent=2).encode()).decode()
            data = {"message": f"Finans Güncelleme: {dosya_adi}", "content": content, "branch": "main"}
            if sha: data["sha"] = sha
            requests.put(url, headers=headers, json=data)
            st.toast(f"GitHub: {dosya_adi} güncellendi! ✅")
    except Exception as e:
        st.error(f"Sistem Hatası: {str(e)}")

# --- VERİ YÖNETİMİ ---
def veri_yukle(dosya_adi, varsayilan):
    if not os.path.exists(dosya_adi): return varsayilan
    with open(dosya_adi, "r") as f:
        try:
            data = json.load(f)
            if dosya_adi == "varliklarim.json":
                for kat in data:
                    for vid in data[kat]:
                        if not isinstance(data[kat][vid], dict):
                            data[kat][vid] = {"miktar": data[kat][vid], "maliyet_usd": 0.0}
            return data
        except: return varsayilan

# Sayfa Ayarları
st.set_page_config(page_title="Finans Karargahı", layout="wide")

# Verileri Yükle
veriler = veri_yukle("varliklarim.json", {"hisseler": {}, "kripto_paralar": {}, "nakit_ve_emtia": {}})
gecmis_fiyatlar = veri_yukle("fiyat_gecmis.json", {})
gecmis_kayitlar = [k for k in veri_yukle("gecmis_arsiv.json", []) if "nan" not in str(k)]
butce_verisi = veri_yukle("butce.json", {"gelirler": {}, "giderler": {"Kredi Kartlari": {}, "Diger Borclar": {}, "Sabit Giderler": {}}})

# --- YARDIMCI FONKSİYONLAR ---
def temizle_sayi(v):
    if isinstance(v, str): return float(v.replace("₺", "").replace("$", "").replace(",", "").replace("%", "").strip())
    return float(v)

def fmt_yuzde(suan, eski):
    try:
        s, e = temizle_sayi(suan), temizle_sayi(eski)
        return ((s - e) / e) * 100 if e != 0 else 0.0
    except: return 0.0

def renk_stili(val):
    if isinstance(val, (int, float)):
        color = "red" if val < 0 else "green" if val > 0 else "white"
        return f"color: {color}"
    return ""

def doviz_cek():
    try:
        res = requests.get("https://www.doviz.com/", timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        def t(sid): return float(soup.find("span", {"data-socket-key": sid}).text.strip().replace(".", "").replace(",", "."))
        return {"USD": t("USD"), "EUR": t("EUR"), "GBP": t("GBP"), "gram-altin": t("gram-altin")}
    except: return {"USD": gecmis_fiyatlar.get("USD_tl", 43.15)}

def kripto_fiyat_cek(kripto_sozlugu):
    ids = ",".join(kripto_sozlugu.keys())
    if not ids: return {}
    try: return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd", timeout=5).json()
    except: return {}

def hisse_fiyat_cek(hisse_listesi):
    res = {}
    for h in hisse_listesi:
        try:
            t_obj = yf.Ticker(h)
            hist = t_obj.history(period="1d")
            f = hist["Close"].iloc[-1] if not hist.empty else 0
            if (h.upper() == "GMSTR.IS" and f < 100) or f <= 0:
                r = requests.get(f"https://borsa.doviz.com/hisseler/{h.split('.')[0].lower()}", timeout=5)
                f = float(BeautifulSoup(r.text, "html.parser").find("div", {"class": "text-xl font-semibold"}).text.strip().replace(".", "").replace(",", "."))
            res[h] = f
        except: res[h] = 0
    return res

@st.cache_data(ttl=3600)
def ai_analiz_uret(varlik_adi, degisim):
    if "GEMINI_API_KEY" not in st.secrets: return "Analiz kapalı."
    try:
        prompt = f"{varlik_adi} varlığı son dönemde %{degisim:.1f} performans gösterdi. Güncel piyasa koşullarına göre nedenini 12 kelimede özetle."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Veri akışı şu an kısıtlı."

# --- NAVİGASYON ---
st.sidebar.title("💳 Finans Merkezi")
sayfa = st.sidebar.radio("Menü:", ["Ana Panel", "Geçmiş Performans", "Bütçe Yönetimi"])

# --- ANA PANEL ---
if sayfa == "Ana Panel":
    st.title("🚀 Varlık Kontrol Paneli")
    kurlar = doviz_cek()
    usd_try = kurlar.get("USD", 43.15)
    k_fiyatlar = kripto_fiyat_cek(veriler["kripto_paralar"])
    h_fiyatlar = hisse_fiyat_cek(veriler["hisseler"].keys())

    analiz_listesi = []
    toplam_maliyet_usd = 0

    def ciz_tablo(kat, varliklar, kaynak, tip):
        global toplam_maliyet_usd
        liste = []
        t_tl, t_usd = 0, 0
        for vid, data in varliklar.items():
            mik, mal_usd = data["miktar"], data["maliyet_usd"]
            if tip == "kripto":
                f_usd = kaynak.get(vid, {}).get("usd", 0)
                if f_usd <= 0: f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
                f_tl = f_usd * usd_try
            else:
                f_tl = kaynak.get(vid, 0) if tip == "hisse" else kurlar.get({"dolar":"USD","euro":"EUR","gram_altin":"gram-altin"}.get(vid), 0)
                if f_tl <= 0: f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
                f_usd = f_tl / usd_try

            kz_yuzde = ((f_usd - mal_usd) / mal_usd * 100) if mal_usd > 0 else 0
            t_tl += mik * f_tl
            t_usd += mik * f_usd
            toplam_maliyet_usd += (mik * mal_usd)

            analiz_notu = ai_analiz_uret(vid.upper(), kz_yuzde)
            
            row = {
                "Varlık": vid.upper(), "Miktar": mik, "Maliyet ($)": mal_usd, "Birim Fiyat ($)": f_usd,
                "K/Z %": kz_yuzde, "Değer (TL)": mik * f_tl, "Değer ($)": mik * f_usd, "Analiz": analiz_notu
            }
            liste.append(row)
            analiz_listesi.append(row)
            gecmis_fiyatlar[f"{vid}_tl"], gecmis_fiyatlar[f"{vid}_usd"] = f_tl, f_usd

        st.subheader(kat.replace("_", " ").title())
        if liste:
            st.dataframe(pd.DataFrame(liste).style.format({
                "Maliyet ($)": "${:,.2f}", "Birim Fiyat ($)": "${:,.2f}", "K/Z %": "{:+.2f}%",
                "Değer (TL)": "₺{:,.2f}", "Değer ($)": "${:,.2f}"
            }).applymap(renk_stili, subset=["K/Z %"]), use_container_width=True)
        return {"tl": t_tl, "usd": t_usd}

    res_k = ciz_tablo("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto")
    res_n = ciz_tablo("nakit_ve_emtia", veriler["nakit_ve_emtia"], None, "nakit")
    res_h = ciz_tablo("hisseler", veriler["hisseler"], h_fiyatlar, "hisse")

    g_tl = res_k["tl"] + res_n["tl"] + res_h["tl"]
    g_usd = res_k["usd"] + res_n["usd"] + res_h["usd"]

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"₺{g_tl:,.2f}")
    c2.metric("GENEL TOPLAM ($)", f"${g_usd:,.2f}")
    c3.metric("Dolar Kuru", f"₺{usd_try}")

    # --- RİSK ANALİZİ ---
    st.markdown("### ⚖️ Portföy Risk ve Dağılım Analizi")
    gumus_tl = (gecmis_fiyatlar.get("GMSTR.IS_tl", 0) * veriler["hisseler"].get("GMSTR.IS", {"miktar":0})["miktar"])
    altin_tl = (gecmis_fiyatlar.get("GLDTR.IS_tl", 0) * veriler["hisseler"].get("GLDTR.IS", {"miktar":0})["miktar"])
    
    riskli_hisse = max(0, res_h["tl"] - (gumus_tl + altin_tl))
    guvenli = res_n["tl"]
