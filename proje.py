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

# --- GITHUB OTOMATIK KAYIT ---
def github_a_kaydet(dosya_adi, veri):
    with open(dosya_adi, "w") as f:
        json.dump(veri, f, indent=2)
    if "GITHUB_TOKEN" in st.secrets:
        try:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            url = f"https://api.github.com/repos/{repo}/contents/{dosya_adi}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            r = requests.get(url, headers=headers)
            sha = r.json().get("sha") if r.status_code == 200 else None
            content = base64.b64encode(json.dumps(veri, indent=2).encode()).decode()
            data = {"message": "Guncelleme", "content": content, "branch": "main"}
            if sha: data["sha"] = sha
            requests.put(url, headers=headers, json=data)
        except: pass

# --- VERI YUKLE (HATA ONARICI) ---
def veri_yukle(dosya_adi, varsayilan):
    if not os.path.exists(dosya_adi): return varsayilan
    with open(dosya_adi, "r") as f:
        try:
            data = json.load(f)
            # AttributeError Onarımı: Sayı olan verileri sözlüğe çevir
            if dosya_adi == "varliklarim.json":
                for kat in data:
                    for vid in data[kat]:
                        if not isinstance(data[kat][vid], dict):
                            data[kat][vid] = {"miktar": data[kat][vid], "maliyet_usd": 0.0}
            return data
        except: return varsayilan

st.set_page_config(page_title="Finans Karargahi", layout="wide")

veriler = veri_yukle("varliklarim.json", {"hisseler": {}, "kripto_paralar": {}, "nakit_ve_emtia": {}})
gecmis_fiyatlar = veri_yukle("fiyat_gecmis.json", {})
gecmis_kayitlar = veri_yukle("gecmis_arsiv.json", [])
butce_verisi = veri_yukle("butce.json", {"gelirler": {}, "giderler": {"Kredi Kartlari": {}, "Diger Borclar": {}, "Sabit Giderler": {}}})
butce_arsivi = veri_yukle("butce_arsiv.json", [])

# --- YARDIMCI FONKSIYONLAR ---
def temizle_sayi(v):
    if v is None or v == "" or str(v).lower() == "nan": return 0.0
    if isinstance(v, (int, float)): return float(v)
    try:
        s = str(v).replace("TL","").replace("$","").replace("₺","").replace(",","").replace("%","").strip()
        return float(s)
    except: return 0.0

def fmt_yuzde(suan, eski):
    s, e = temizle_sayi(suan), temizle_sayi(eski)
    return ((s - e) / e) * 100 if e != 0 else 0.0

def renk_stili(val):
    v = temizle_sayi(val)
    return 'color: #ff4b4b' if v < -0.001 else ('color: #00cc96' if v > 0.001 else '')

def doviz_cek():
    try:
        res = requests.get("https://www.doviz.com/", timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        def t(sid): return float(soup.find("span", {"data-socket-key": sid}).text.strip().replace(".", "").replace(",", "."))
        return {"USD": t("USD"), "EUR": t("EUR"), "GBP": t("GBP"), "gram-altin": t("gram-altin")}
    except: return {"USD": 43.12}

def kripto_fiyat_cek(kripto_sozlugu):
    ids = ",".join(kripto_sozlugu.keys())
    return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd").json() if ids else {}

def hisse_fiyat_cek(hisse_listesi):
    res = {}
    for h in hisse_listesi:
        try:
            t = yf.Ticker(h); hist = t.history(period="1d")
            res[h] = hist['Close'].iloc[-1] if not hist.empty else 0
        except: res[h] = 0
    return res

# --- NAVIGASYON ---
sayfa = st.sidebar.radio("Menu:", ["Ana Panel", "Gecmis Performans", "Butce Yonetimi", "Butce Arsivi"])

if sayfa == "Ana Panel":
    st.title("Varlik Kontrol Paneli")
    kurlar = doviz_cek(); usd_try = kurlar.get("USD", 43.12)
    k_fiyatlar = kripto_fiyat_cek(veriler["kripto_paralar"])
    h_fiyatlar = hisse_fiyat_cek(veriler["hisseler"].keys())

    def ciz_tablo(kat, varliklar, kaynak, tip):
        liste = []; t_tl = 0; t_usd = 0
        for vid, data in varliklar.items():
            mik = data.get("miktar", 0); mal = data.get("maliyet_usd", 0)
            if tip=="kripto":
                f_usd = kaynak.get(vid, {}).get("usd", 0)
                if f_usd <= 0: f_usd = gecmis_fiyatlar.get(vid+"_usd", 0)
                f_tl = f_usd * usd_try
            else:
                f_tl = kaynak.get(vid, 0) if kaynak else kurlar.get({"dolar":"USD","euro":"EUR","gram_altin":"gram-altin"}.get(vid), 0)
                if f_tl <= 0: f_tl = gecmis_fiyatlar.get(vid+"_tl", 0)
                f_usd = f_tl / usd_try
            t_tl += (mik * f_tl); t_usd += (mik * f_usd)
            liste.append({"Varlik": vid.upper(), "Miktar": mik, "Maliyet ($)": mal, "Deger (TL)": mik*f_tl, "Deger ($)": mik*f_usd})
            gecmis_fiyatlar[vid+"_tl"] = f_tl; gecmis_fiyatlar[vid+"_usd"] = f_usd
        if liste: st.dataframe(pd.DataFrame(liste), use_container_width=True)
        return {"tl": t_tl, "usd": t_usd}

    res_k = ciz_tablo("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto")
    res_n = ciz_tablo("nakit_ve_emtia", veriler["nakit_ve_emtia"], None, "nakit")
    res_h = ciz_tablo("hisseler", veriler["hisseler"], h_fiyatlar, "hisse")

    g_tl = res_k['tl'] + res_n['tl'] + res_h['tl']
    g_usd = res_k['usd'] + res_n['usd'] + res_h['usd']
    e_tl = temizle_sayi(gecmis_kayitlar[-1].get("Toplam (TL)")) if gecmis_kayitlar else g_tl
    e_usd = temizle_sayi(gecmis_kayitlar[-1].get("Toplam ($)")) if gecmis_kayitlar else g_usd

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"TL {g_tl:,.2f}", f"{fmt_yuzde(g_tl, e_tl):+.2f}%")
    c2.metric("GENEL TOPLAM ($)", f"$ {g_usd:,.2f}", f"{fmt_yuzde(g_usd, e_usd):+.2f}%")
    c3.metric("Dolar Kuru", f"TL {usd_try}")

    if st.button("GUNU KAPAT"):
        kayit = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "Kripto (TL)": res_k['tl'], "Nakit (TL)": res_n['tl'], "Borsa (TL)": res_h['tl'], "Toplam (TL)": g_tl, "Deg_TL_Num": fmt_yuzde(g_tl, e_tl), "Kripto ($)": res_k['usd'], "Nakit ($)": res_n['usd'], "Borsa ($)": res_h['usd'], "Toplam ($)": g_usd, "Deg_USD_Num": fmt_yuzde(g_usd, e_usd)}
        gecmis_kayitlar.append(kayit); github_a_kaydet("gecmis_arsiv.json", gecmis_kayitlar); st.rerun()

elif sayfa == "Gecmis Performans":
    st.title("Detayli Portfoy Arsivi")
    if gecmis_kayitlar:
        df = pd.DataFrame(gecmis_kayitlar[::-1])
        # Eski kolonları temizle
        df = df.drop(columns=[c for c in ["Değişim (TL)", "Değişim ($)"] if c in df.columns])
        st.dataframe(df.style.applymap(renk_stili, subset=[c for c in ["Deg_TL_Num", "Deg_USD_Num"] if c in df.columns]).format({c: "{:+.2f}%" for c in ["Deg_TL_Num", "Deg_USD_Num"] if c in df.columns}), use_container_width=True)

elif sayfa == "Butce Yonetimi":
    st.title("Butce")
    usd_val = doviz_cek().get("USD", 43.12)
    c1, c2 = st.columns(2)
    with c1:
        y_g = st.text_input("Gelir Ekle")
        if st.button("Gelir Kaydet") and y_g:
            butce_verisi["gelirler"][y_g] = 0.0; github_a_kaydet("butce.json", butce_verisi); st.rerun()
        for k, v in butce_verisi["gelirler"].items():
            butce_verisi["gelirler"][k] = st.number_input(k, value=float(v), key="g_"+k)
        t_gel = sum(butce_verisi["gelirler"].values())
    with c2:
        def but_ciz(a):
            t = 0
            for n, v in butce_verisi["giderler"].get(a, {}).items():
                butce_verisi["giderler"][a][n] = st.number_input(n, value=float(v), key="v_"+a+"_"+n)
                t += butce_verisi["giderler"][a][n]
            return t
        t_gid = but_ciz("Kredi Kartlari") + but_ciz("Sabit Giderler") + but_ciz("Diger Borclar")
    net = t_gel - t_gid
    st.header(f"Net: TL {net:,.2f}")
    e_net = temizle_sayi(butce_arsivi[-1].get("NET (TL)")) if butce_arsivi else net
    if st.button("ARSIVLE"):
        butce_arsivi.append({"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "GELIR (TL)": t_gel, "GIDER (TL)": t_gid, "NET (TL)": net, "NET ($)": net/usd_val, "Degisim_Num": fmt_yuzde(net, e_net)})
        github_a_kaydet("butce_arsiv.json", butce_arsivi); st.rerun()

elif sayfa == "Butce Arsivi":
    st.title("Butce Arsivi")
    if butce_arsivi:
        df = pd.DataFrame(butce_arsivi[::-1])
        df = df.drop(columns=[c for c in ["Değişim %"] if c in df.columns])
        st.dataframe(df.style.applymap(renk_stili, subset=["Degisim_Num"] if "Degisim_Num" in df.columns else []).format({"Degisim_Num": "{:+.2f}%"}), use_container_width=True)

with st.sidebar.expander("Varlik Ekle"):
    kat = st.selectbox("Kat", ["hisseler", "kripto_paralar", "nakit_ve_emtia"])
    kod = st.text_input("Kod").lower()
    mik = st.number_input("Mik", value=0.0)
    mal = st.number_input("Mal ($)", value=0.0)
    if st.button("Varlik Kaydet"):
        veriler[kat][kod] = {"miktar": mik, "maliyet_usd": mal}
        github_a_kaydet("varliklarim.json", veriler); st.rerun()
