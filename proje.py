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

# --- GITHUB OTOMATIK KAYIT FONKSIYONU ---
def github_a_kaydet(dosya_adi, veri):
    try:
        with open(dosya_adi, "w") as f:
            json.dump(veri, f, indent=2)

        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            url = f"https://api.github.com/repos/{repo}/contents/{dosya_adi}"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            r = requests.get(url, headers=headers)
            sha = r.json().get("sha") if r.status_code == 200 else None

            content = base64.b64encode(json.dumps(veri, indent=2).encode()).decode()
            data = {
                "message": f"Finans Güncelleme: {dosya_adi} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": content,
                "branch": "main",
            }
            if sha:
                data["sha"] = sha

            put_res = requests.put(url, headers=headers, json=data)
            
            if put_res.status_code not in [200, 201]:
                st.error(f"GitHub Hatası ({dosya_adi}): {put_res.json().get('message')}")
            else:
                st.toast(f"GitHub: {dosya_adi} güncellendi! ✅")
    except Exception as e:
        st.error(f"Sistem Hatası: {str(e)}")

# --- VERİ YÖNETİMİ ---
def veri_yukle(dosya_adi, varsayilan):
    if not os.path.exists(dosya_adi):
        return varsayilan
    with open(dosya_adi, "r") as f:
        try:
            data = json.load(f)
            # Varlık yapısını modernize et (eski sürümden geçiş için)
            if dosya_adi == "varliklarim.json":
                for kat in data:
                    for vid in data[kat]:
                        if not isinstance(data[kat][vid], dict):
                            data[kat][vid] = {"miktar": data[kat][vid], "maliyet_usd": 0.0}
            return data
        except:
            return varsayilan

# Sayfa Ayarları
st.set_page_config(page_title="Finans Karargahı", layout="wide")

# Verileri Yükle
veriler = veri_yukle("varliklarim.json", {"hisseler": {}, "kripto_paralar": {}, "nakit_ve_emtia": {}})
gecmis_fiyatlar = veri_yukle("fiyat_gecmis.json", {})
gecmis_kayitlar = [k for k in veri_yukle("gecmis_arsiv.json", []) if "nan" not in str(k)]
butce_verisi = veri_yukle("butce.json", {"gelirler": {}, "giderler": {"Kredi Kartlari": {}, "Diger Borclar": {}, "Sabit Giderler": {}}})
butce_arsivi = [b for b in veri_yukle("butce_arsiv.json", []) if "nan" not in str(b)]
ai_yorumlari = veri_yukle("ai_yorumlar.json", {"son_yorum": "Henüz analiz yapılmadı. Butona basarak başlayın.", "tarih": "-"})

# --- YARDIMCI FONKSİYONLAR ---
def fmt_yuzde(suan, eski):
    try:
        s, e = float(suan), float(eski)
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
        def t(sid):
            val = soup.find("span", {"data-socket-key": sid}).text.strip().replace(".", "").replace(",", ".")
            return float(val)
        return {"USD": t("USD"), "EUR": t("EUR"), "GBP": t("GBP"), "gram-altin": t("gram-altin")}
    except:
        return {"USD": gecmis_fiyatlar.get("USD_tl", 35.0)}

def kripto_fiyat_cek(kripto_sozlugu):
    ids = ",".join(kripto_sozlugu.keys())
    if not ids: return {}
    try:
        return requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd", timeout=5).json()
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

# --- MODÜLER HESAPLAMA VE GÖSTERİM ---
def hesapla_varlik_verileri(kat, varliklar, kaynak, tip, usd_try, kurlar):
    liste = []
    t_tl, t_usd, t_e_tl, t_e_usd = 0, 0, 0, 0
    for vid, data in varliklar.items():
        mik, mal_usd = data["miktar"], data["maliyet_usd"]
        if tip == "kripto":
            f_usd = kaynak.get(vid, {}).get("usd", 0)
            if f_usd <= 0: f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
            f_tl = f_usd * usd_try
        else:
            d_harita = {"dolar": "USD", "euro": "EUR", "sterlin": "GBP", "gram_altin": "gram-altin"}
            f_tl = kaynak.get(vid, 0) if tip == "hisse" else kurlar.get(d_harita.get(vid), 0)
            if f_tl <= 0: f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
            f_usd = f_tl / usd_try if usd_try > 0 else 0

        val_tl = mik * f_tl
        val_usd = mik * f_usd
        t_tl += val_tl
        t_usd += val_usd
        t_e_tl += mik * gecmis_fiyatlar.get(f"{vid}_tl", f_tl)
        t_e_usd += mik * gecmis_fiyatlar.get(f"{vid}_usd", f_usd)

        liste.append({
            "Varlık": vid.upper(), "Miktar": mik, "Maliyet ($)": mal_usd, "Birim Fiyat ($)": f_usd,
            "K/Z %": ((f_usd - mal_usd) / mal_usd * 100) if mal_usd > 0 else 0,
            "Değer (TL)": val_tl, "Değ% (TL)": fmt_yuzde(f_tl, gecmis_fiyatlar.get(f"{vid}_tl", f_tl)),
            "Değer ($)": val_usd, "Değ% ($)": fmt_yuzde(f_usd, gecmis_fiyatlar.get(f"{vid}_usd", f_usd)),
        })
        gecmis_fiyatlar[f"{vid}_tl"], gecmis_fiyatlar[f"{vid}_usd"] = f_tl, f_usd
    return liste, {"tl": t_tl, "usd": t_usd, "e_tl": t_e_tl, "e_usd": t_e_usd}

def tablo_goster(baslik, veri_listesi, toplamlar):
    st.subheader(baslik)
    if veri_listesi:
        df = pd.DataFrame(veri_listesi)
        st.dataframe(df.style.format({
            "Maliyet ($)": "${:,.2f}", "Birim Fiyat ($)": "${:,.2f}", "K/Z %": "{:+.2f}%",
            "Değer (TL)": "₺{:,.2f}", "Değer ($)": "${:,.2f}", "Değ% (TL)": "{:+.2f}%", "Değ% ($)": "{:+.2f}%",
        }).applymap(renk_stili, subset=["K/Z %", "Değ% (TL)", "Değ% ($)"]), use_container_width=True)
        st.info(f"**Ara Toplam:** ₺{toplamlar['tl']:,.2f} | ${toplamlar['usd']:,.2f}")

# --- AI ANALİZ ---
def ai_analiz_al(listeler):
    if "GEMINI_API_KEY" not in st.secrets: return "API Key Ayarlanmamış."
    tum = [v for l in listeler for v in l]
    sirali = sorted(tum, key=lambda x: abs(x["Değ% ($)"]), reverse=True)[:5]
    metin = ", ".join([f"{v['Varlık']} (%{v['Değ% ($)']:+.2f})" for v in sirali])
    prompt = f"Portföyümdeki en hareketli varlıklar: {metin}. Bu değişimlerin nedenlerini küresel finans haberlerine dayanarak 3 kısa cümlede açıkla."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={st.secrets['GEMINI_API_KEY']}"
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "Analiz şu an yapılamıyor."

# --- NAVİGASYON ---
st.sidebar.title("💳 Finans Merkezi")
sayfa = st.sidebar.radio("Menü:", ["Ana Panel", "Geçmiş Performans", "Bütçe Yönetimi", "Bütçe Arşivi"])

# --- ANA PANEL ---
if sayfa == "Ana Panel":
    st.title("🚀 Varlık Kontrol Paneli")
    kurlar = doviz_cek()
    usd_try = kurlar.get("USD", 35.0)
    k_fiyatlar = kripto_fiyat_cek(veriler["kripto_paralar"])
    h_fiyatlar = hisse_fiyat_cek(veriler["hisseler"].keys())

    l_k, r_k = hesapla_varlik_verileri("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto", usd_try, kurlar)
    l_n, r_n = hesapla_varlik_verileri("nakit_ve_emtia", veriler["nakit_ve_emtia"], kurlar, "nakit", usd_try, kurlar)
    l_h, r_h = hesapla_varlik_verileri("hisseler", veriler["hisseler"], h_fiyatlar, "hisse", usd_try, kurlar)

    # --- AI YORUM BLOĞU ---
    with st.expander("🤖 Yapay Zeka Piyasa Analizi", expanded=True):
        st.caption(f"Son Analiz: {ai_yorumlari['tarih']}")
        st.write(ai_yorumlari['son_yorum'])
        if st.button("Piyasayı Şimdi Yorumla"):
            y_y = ai_analiz_al([l_k, l_n, l_h])
            ai_yorumlari = {"son_yorum": y_y, "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")}
            github_a_kaydet("ai_yorumlar.json", ai_yorumlari)
            st.rerun()

    tablo_goster("Kripto Paralar", l_k, r_k)
    tablo_goster("Nakit ve Emtia", l_n, r_n)
    tablo_goster("Hisseler", l_h, r_h)

    # Genel Toplamlar
    g_tl = r_k["tl"] + r_n["tl"] + r_h["tl"]
    g_usd = r_k["usd"] + r_n["usd"] + r_h["usd"]
    e_tl = r_k["e_tl"] + r_n["e_tl"] + r_h["e_tl"]
    e_usd = r_k["e_usd"] + r_n["e_usd"] + r_h["e_usd"]

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"₺{g_tl:,.2f}", f"{fmt_yuzde(g_tl, e_tl):+.2f}%")
    c2.metric("GENEL TOPLAM ($)", f"${g_usd:,.2f}", f"{fmt_yuzde(g_usd, e_usd):+.2f}%")
    c3.metric("Dolar Kuru", f"₺{usd_try}")

    # Risk Analizi
    st.markdown("### ⚖️ Risk Analizi")
    gumus_tl = sum(d["Değer (TL)"] for d in l_h if "GMSTR" in d["Varlık"])
    altin_tl = sum(d["Değer (TL)"] for d in l_h if "GLDTR" in d["Varlık"])
    riskli_h = max(0, r_h["tl"] - (gumus_tl + altin_tl))
    guvenli = r_n["tl"] + gumus_tl + altin_tl
    toplam_s = max(1, riskli_h + guvenli + r_k["tl"])
    
    analiz_data = [
        {"Sınıf": "Hisse (Şirket)", "Oran": (riskli_h/toplam_s)*100, "İdeal": 25},
        {"Sınıf": "Güvenli Liman", "Oran": (guvenli/toplam_s)*100, "İdeal": 45},
        {"Sınıf": "Kripto (Yüksek Risk)", "Oran": (r_k["tl"]/toplam_s)*100, "İdeal": 30}
    ]
    st.table(pd.DataFrame(analiz_data))

    if st.button("💰 GÜNÜ KAPAT"):
        kayit = {"tarih": datetime.now().strftime("%Y-%m-%d %H:%M"), "Toplam (TL)": f"₺{g_tl:,.0f}", "Değişim (TL)": f"{fmt_yuzde(g_tl, e_tl):+.2f}%", "Toplam ($)": f"${g_usd:,.0f}", "Değişim ($)": f"{fmt_yuzde(g_usd, e_usd):+.2f}%"}
        gecmis_kayitlar.append(kayit)
        github_a_kaydet("gecmis_arsiv.json", gecmis_kayitlar)
        github_a_kaydet("fiyat_gecmis.json", gecmis_fiyatlar)
        st.success("Arşivlendi!")

# --- SAYFALAR: GEÇMİŞ, BÜTÇE VS ---
elif sayfa == "Geçmiş Performans":
    st.title("📜 Arşiv")
    if not gecmis_kayitlar: st.info("Kayıt yok.")
    else: st.dataframe(pd.DataFrame(gecmis_kayitlar[::-1]), use_container_width=True)

elif sayfa == "Bütçe Yönetimi":
    st.title("📊 Bütçe")
    usd_val = doviz_cek().get("USD", 35.0)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Gelirler")
        y_g = st.text_input("Gelir Adı")
        if st.button("Gelir Ekle") and y_g:
            butce_verisi["gelirler"][y_g] = 0.0
            github_a_kaydet("butce.json", butce_verisi)
            st.rerun()
        for k, v in butce_verisi["gelirler"].items():
            butce_verisi["gelirler"][k] = st.number_input(k, value=float(v), key=f"g_{k}")
        t_gel = sum(butce_verisi["gelirler"].values())
        st.success(f"Toplam Gelir: ₺{t_gel:,.2f}")

    with col2:
        st.subheader("Giderler")
        t_gid = 0
        for kat in butce_verisi["giderler"]:
            st.write(f"**{kat}**")
            y_gid = st.text_input(f"{kat} Ekle", key=f"new_{kat}")
            if st.button(f"Ekle", key=f"btn_{kat}") and y_gid:
                butce_verisi["giderler"][kat][y_gid] = 0.0
                github_a_kaydet("butce.json", butce_verisi)
                st.rerun()
            for n, v in butce_verisi["giderler"][kat].items():
                butce_verisi["giderler"][kat][n] = st.number_input(n, value=float(v), key=f"gid_{kat}_{n}")
                t_gid += butce_verisi["giderler"][kat][n]
        st.error(f"Toplam Gider: ₺{t_gid:,.2f}")

    net = t_gel - t_gid
    st.header(f"Net Durum: ₺{net:,.2f}")
    if st.button("💾 BÜTÇEYİ ARŞİVLE"):
        butce_arsivi.append({"tarih": datetime.now().strftime("%Y-%m-%d"), "Gelir": t_gel, "Gider": t_gid, "Net": net})
        github_a_kaydet("butce_arsiv.json", butce_arsivi)
        st.success("Bütçe arşivlendi.")

elif sayfa == "Bütçe Arşivi":
    st.title("📜 Bütçe Arşivi")
    if not butce_arsivi: st.info("Kayıt yok.")
    else: st.dataframe(pd.DataFrame(butce_arsivi[::-1]), use_container_width=True)

# --- SIDEBAR: VARLIK YÖNETİMİ ---
with st.sidebar.expander("➕ Varlık Yönetimi"):
    kat_sec = st.selectbox("Kategori", ["hisseler", "kripto_paralar", "nakit_ve_emtia"])
    kod_sec = st.text_input("Kod (Örn: btc, thyao.is)").lower().strip()
    mik_sec = st.number_input("Toplam Miktar", value=0.0, format="%.6f")
    fiy_sec = st.number_input("Son Alım Fiyatı ($)", value=0.0, format="%.4f")
    
    c1, c2 = st.columns(2)
    if c1.button("Güncelle"):
        if kod_sec:
            old = veriler[kat_sec].get(kod_sec, {"miktar": 0, "maliyet_usd": 0})
            # Ağırlıklı Ortalama Maliyet Hesaplama
            if mik_sec > old["miktar"] and fiy_sec > 0:
                yeni_maliyet = ((old["miktar"] * old["maliyet_usd"]) + ((mik_sec - old["miktar"]) * fiy_sec)) / mik_sec
            else:
                yeni_maliyet = fiy_sec if fiy_sec > 0 else old["maliyet_usd"]
            veriler[kat_sec][kod_sec] = {"miktar": mik_sec, "maliyet_usd": yeni_maliyet}
            github_a_kaydet("varliklarim.json", veriler)
            st.rerun()
    if c2.button("Sil"):
        if kod_sec in veriler[kat_sec]:
            del veriler[kat_sec][kod_sec]
            github_a_kaydet("varliklarim.json", veriler)
            st.rerun()
