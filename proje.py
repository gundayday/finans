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

# --- GITHUB OTOMATIK KAYDET FONKSIYONU ---
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
            data = {"message": f"Veri Güncelleme: {dosya_adi}", "content": content, "branch": "main"}
            if sha: data["sha"] = sha
            requests.put(url, headers=headers, json=data)
        except: pass

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

st.set_page_config(page_title="Finans Karargahı", layout="wide")

veriler = veri_yukle("varliklarim.json", {"hisseler": {}, "kripto_paralar": {}, "nakit_ve_emtia": {}})
gecmis_fiyatlar = veri_yukle("fiyat_gecmis.json", {})
gecmis_kayitlar = veri_yukle("gecmis_arsiv.json", [])
butce_verisi = veri_yukle("butce.json", {"gelirler": {}, "giderler": {"Kredi Kartlari": {}, "Diger Borclar": {}, "Sabit Giderler": {}}})
butce_arsivi = veri_yukle("butce_arsiv.json", [])

# --- YARDIMCI FONKSİYONLAR (HATA KORUMALI) ---
def temizle_sayi(v):
    if v is None or v == "" or str(v).lower() == "nan": return 0.0
    if isinstance(v, (int, float)): return float(v)
    try:
        s = str(v).replace("₺","").replace("$","").replace(",","").replace("%","")
        s = s.replace(":green[","").replace(":red[","").replace("]","").strip()
        return float(s)
    except: return 0.0

def fmt_yuzde(suan, eski):
    s = temizle_sayi(suan); e = temizle_sayi(eski)
    if e == 0: return 0.0
    return ((s - e) / e) * 100

def renk_stili(val):
    v = temizle_sayi(val)
    if v < -0.01: return 'color: #ff4b4b' # Kırmızı
    if v > 0.01: return 'color: #00cc96' # Yeşil
    return ''

def doviz_cek():
    try:
        res = requests.get("https://www.doviz.com/", timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        def t(sid): return float(soup.find("span", {"data-socket-key": sid}).text.strip().replace(".", "").replace(",", "."))
        return {"USD": t("USD"), "EUR": t("EUR"), "GBP": t("GBP"), "gram-altin": t("gram-altin")}
    except: return {"USD": 43.12}

def kripto_fiyat_cek(kripto_sozlugu):
    ids = ",".join(kripto_sozlugu.keys())
    if not ids: return {}
    try: return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd", timeout=5).json()
    except: return {}

def hisse_fiyat_cek(hisse_listesi):
    res = {}
    for h in hisse_listesi:
        try:
            t_obj = yf.Ticker(h); hist = t_obj.history(period="1d")
            f = hist['Close'].iloc[-1] if not hist.empty else 0
            if (h.upper() == "GMSTR.IS" and f < 100) or f <= 0:
                r = requests.get(f"https://borsa.doviz.com/hisseler/{h.split('.')[0].lower()}", timeout=5)
                f = float(BeautifulSoup(r.text, "html.parser").find("div", {"class": "text-xl font-semibold"}).text.strip().replace(".", "").replace(",", "."))
            res[h] = f
        except: res[h] = 0
    return res

# --- NAVİGASYON ---
st.sidebar.title("💳 Finans Merkezi")
sayfa = st.sidebar.radio("Menü:", ["Ana Panel", "Geçmiş Performans", "Bütçe Yönetimi", "Bütçe Arşivi"])

# --- ANA PANEL ---
if sayfa == "Ana Panel":
    st.title("🚀 Varlık Kontrol Paneli")
    kurlar = doviz_cek(); usd_try = kurlar.get("USD", 43.12)
    k_fiyatlar = kripto_fiyat_cek(veriler["kripto_paralar"])
    h_fiyatlar = hisse_fiyat_cek(veriler["hisseler"].keys())

    if 'man_f' not in st.session_state: st.session_state.man_f = {}

    def ciz_tablo(kat, varliklar, kaynak, tip):
        liste = []; t_tl = 0; t_usd = 0; t_e_tl = 0; t_e_usd = 0
        for vid, data in varliklar.items():
            mik = data["miktar"]; mal_usd = data["maliyet_usd"]
            man = st.session_state.man_f.get(f"m_{kat}_{vid}", 0)
            if tip=="kripto":
                f_usd = man if man > 0 else kaynak.get(vid, {}).get("usd", 0)
                if f_usd <= 0: f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
                f_tl = f_usd * usd_try
            else:
                f_tl = man if man > 0 else (kaynak.get(vid, 0) if tip=="hisse" else kurlar.get({"dolar":"USD","euro":"EUR","sterlin":"GBP","gram_altin":"gram-altin"}.get(vid), 0))
                if (vid.lower() == "gmstr.is" and f_tl < 100) or f_tl <= 0: f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
                f_usd = f_tl / usd_try
            
            mal_usd = f_usd if mal_usd == 0 else mal_usd
            e_f_tl = gecmis_fiyatlar.get(f"{vid}_tl", f_tl); e_f_usd = gecmis_fiyatlar.get(f"{vid}_usd", f_usd)
            t_tl += (mik * f_tl); t_usd += (mik * f_usd); t_e_tl += (mik * e_f_tl); t_e_usd += (mik * e_f_usd)
            
            liste.append({
                "Varlık": vid.upper(), "Miktar": mik, "Maliyet ($)": mal_usd, 
                "Değer (TL)": mik*f_tl, "Değ% (TL)": fmt_yuzde(f_tl, e_f_tl), 
                "Değer ($)": mik*f_usd, "Değ% ($)": fmt_yuzde(f_usd, e_f_usd)
            })
            gecmis_fiyatlar[f"{vid}_tl"] = f_tl; gecmis_fiyatlar[f"{vid}_usd"] = f_usd

        st.subheader(kat.replace("_", " ").title())
        if liste:
            df = pd.DataFrame(liste)
            st.dataframe(df.style.applymap(renk_stili, subset=["Değ% (TL)", "Değ% ($)"]), use_container_width=True)
            st.info(f"**Ara Toplam:** ₺{t_tl:,.2f} | ${t_usd:,.2f}")
        return {"tl": t_tl, "usd": t_usd}

    res_k = ciz_tablo("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto")
    res_n = ciz_tablo("nakit_ve_emtia", veriler["nakit_ve_emtia"], None, "nakit")
    res_h = ciz_tablo("hisseler", veriler["hisseler"], h_fiyatlar, "hisse")

    g_tl = res_k['tl'] + res_n['tl'] + res_h['tl']
    g_usd = res_k['usd'] + res_n['usd'] + res_h['usd']
    e_tl = temizle_sayi(gecmis_kayitlar[-1].get("Toplam (TL)", g_tl)) if gecmis_kayitlar else g_tl
    e_usd = temizle_sayi(gecmis_kayitlar[-1].get("Toplam ($)", g_usd)) if gecmis_kayitlar else g_usd

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"₺{g_tl:,.2f}", f"{fmt_yuzde(g_tl, e_tl):+.2f}%")
    c2.metric("GENEL TOPLAM ($)", f"${g_usd:,.2f}", f"{fmt_yuzde(g_usd, e_usd):+.2f}%")
    c3.metric("Dolar Kuru", f"₺{usd_try}")

    if st.button("💰 GÜNÜ KAPAT"):
        kayit = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Kripto (TL)": res_k['tl'], "Nakit (TL)": res_n['tl'], "Borsa (TL)": res_h['tl'],
            "Toplam (TL)": g_tl, "Deg_TL_Num": fmt_yuzde(g_tl, e_tl),
            "Kripto ($)": res_k['usd'], "Nakit ($)": res_n['usd'], "Borsa ($)": res_h['usd'],
            "Toplam ($)": g_usd, "Deg_USD_Num": fmt_yuzde(g_usd, e_usd)
        }
        gecmis_kayitlar.append(kayit)
        github_a_kaydet("gecmis_arsiv.json", gecmis_kayitlar)
        github_a_kaydet("fiyat_gecmis.json", gecmis_fiyatlar)
        st.success("GitHub'a arşivlendi!"); st.rerun()

# --- GEÇMİŞ PERFORMANS ---
elif sayfa == "Geçmiş Performans":
    st.title("📜 Detaylı Portföy Arşivi")
    if not gecmis_kayitlar:
        st.info("Henüz kayıt bulunmuyor.")
    else:
        df_a = pd.DataFrame(gecmis_kayitlar[::-1])
        # Tablodan eski metin tabanlı değişim sütunlarını temizle
        cols_to_drop = ["Değişim (TL)", "Değişim ($)", "Değ% (TL)", "Değ% ($)"]
        df_a = df_a.drop(columns=[c for c in cols_to_drop if c in df_a.columns])
        
        # Sayısal değerleri garantiye al
        for col in ["Deg_TL_Num", "Deg_USD_Num"]:
            if col in df_a.columns:
                df_a[col] = df_a[col].apply(temizle_sayi)
        
        # Hata Çözümü: Formatlama işlemini daha güvenli yapıyoruz
        st.dataframe(
            df_a.style.applymap(renk_stili, subset=[c for c in ["Deg_TL_Num", "Deg_USD_Num"] if c in df_a.columns]),
            use_container_width=True
        )

# --- BÜTÇE ---
elif sayfa == "Bütçe Yönetimi":
    st.title("📊 Bütçe")
    usd_val = doviz_cek().get("USD", 43.12)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Gelir")
        y_g = st.text_input("Gelir Adı Ekle")
        if st.button("Ekle", key="gelir_btn"):
            if y_g: butce_verisi["gelirler"][y_g] = 0.0; github_a_kaydet("butce.json", butce_verisi); st.rerun()
        for k, v in butce_verisi["gelirler"].items():
            butce_verisi["gelirler"][k] = st.number_input(f"{k}", value=float(v), key=f"gel_{k}")
        t_gel = sum(butce_verisi['gelirler'].values())
        st.success(f"Toplam: ₺{t_gel:,.2f}")
    with c2:
        st.subheader("Gider")
        def but_ciz(b, a):
            t = 0; st.write(f"**{b}**")
            for n, v in butce_verisi["giderler"].get(a, {}).items():
                butce_verisi["giderler"][a][n] = st.number_input(f"{n}", value=float(v), key=f"v_{a}_{n}")
                t += butce_verisi["giderler"][a][n]
            return t
        t_gid = but_ciz("Kartlar", "Kredi Kartlari") + but_ciz("Sabit", "Sabit Giderler") + but_ciz("Diğer", "Diger Borclar")
        st.error(f"Toplam: ₺{t_gid:,.2f}")
    
    net = t_gel - t_gid
    st.header(f"Net Bütçe: ₺{net:,.2f}")
    e_net = temizle_sayi(butce_arsivi[-1].get("NET (TL)", net)) if butce_arsivi else net

    if st.button("💾 ARŞİVLE"):
        b_k = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), 
            "GELİR (TL)": t_gel, "GİDER (TL)": t_gid, "NET (TL)": net, 
            "NET ($)": net/usd_val, "Değişim_Num": fmt_yuzde(net, e_net)
        }
        butce_arsivi.append(b_k); github_a_kaydet("butce_arsiv.json", butce_arsivi); st.success("Arşivlendi!"); st.rerun()

elif sayfa == "Bütçe Arşivi":
    st.title("📜 Bütçe Arşivi")
    if not butce_arsivi:
        st.info("Yok.")
    else:
        df_b = pd.DataFrame(butce_arsivi[::-1])
        if "Değişim %" in df_b.columns: df_b = df_b.drop(columns=["Değişim %"])
        if "Değişim_Num" in df_b.columns: df_b["Değişim_Num"] = df_b["Değişim_Num"].apply(temizle_sayi)
        
        st.dataframe(
            df_b.style.applymap(renk_stili, subset=["Değişim_Num"] if "Değişim_Num" in df_b.columns else []), 
            use_container_width=True
        )

with st.sidebar.expander("➕ Varlık & Akıllı Maliyet", expanded=True):
    kat = st.selectbox("Kategori", ["hisseler", "kripto_paralar", "nakit_ve_emtia"])
    kod = st.text_input("Kod").lower()
    m = st.number_input("Miktar", value=0.0, format="%.8f")
    f = st.number_input("Alım Fiyatı ($)", value=0.0, format="%.4f")
    if st.button("Kaydet"):
        old = veriler[kat].get(kod, {"miktar": 0, "maliyet_usd": 0})
        new_c = ((old["miktar"] * old["maliyet_usd"]) + ((m - old["miktar"]) * f)) / m if m > old["miktar"] and f > 0 else (f if old["maliyet_usd"] == 0 else old["maliyet_usd"])
        veriler[kat][kod] = {"miktar": m, "maliyet_usd": new_c}
        github_a_kaydet("varliklarim.json", veriler); st.rerun()
