import streamlit as st
import pandas as pd
import json
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import os
import sys
import subprocess
from datetime import datetime
import plotly.express as px
import numpy as np

# --- GÜVENLİ OTOMATİK BAŞLATICI ---
if __name__ == "__main__":
    if "STREAMLIT_RUN" not in os.environ:
        os.environ["STREAMLIT_RUN"] = "true"
        try:
            subprocess.Popen(["streamlit", "run", sys.argv[0]])
            sys.exit()
        except:
            pass

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finans Karargahı", layout="wide")


# --- 1. VERİ YÖNETİMİ ---
def veri_yukle(dosya_adi, varsayilan):
    if not os.path.exists(dosya_adi):
        with open(dosya_adi, "w") as f:
            json.dump(varsayilan, f)
        return varsayilan
    with open(dosya_adi, "r") as f:
        try:
            data = json.load(f)
            if dosya_adi == "varliklarim.json":
                for kat in data:
                    for vid in data[kat]:
                        if not isinstance(data[kat][vid], dict):
                            data[kat][vid] = {
                                "miktar": data[kat][vid],
                                "maliyet_usd": 0.0,
                            }
            if dosya_adi == "butce.json":
                if "gelirler" not in data:
                    data["gelirler"] = {}
                if "giderler" not in data:
                    data["giderler"] = {}
                for k in ["Kredi Kartlari", "Diger Borclar", "Sabit Giderler"]:
                    if k not in data["giderler"] or not isinstance(
                        data["giderler"][k], dict
                    ):
                        data["giderler"][k] = {}
            return data
        except:
            return varsayilan


def veri_kaydet(dosya_adi, veri):
    with open(dosya_adi, "w") as f:
        json.dump(veri, f, indent=2)


# Verileri Yükle
veriler = veri_yukle(
    "varliklarim.json", {"hisseler": {}, "kripto_paralar": {}, "nakit_ve_emtia": {}}
)
gecmis_fiyatlar = veri_yukle("fiyat_gecmis.json", {})
gecmis_kayitlar = [
    k for k in veri_yukle("gecmis_arsiv.json", []) if "nan" not in str(k)
]
butce_verisi = veri_yukle(
    "butce.json",
    {
        "gelirler": {},
        "giderler": {"Kredi Kartlari": {}, "Diger Borclar": {}, "Sabit Giderler": {}},
    },
)
butce_arsivi = [b for b in veri_yukle("butce_arsiv.json", []) if "nan" not in str(b)]


# --- YARDIMCI FONKSİYONLAR ---
def fmt_deg(suan, eski):
    try:

        def temizle(v):
            if isinstance(v, str):
                return float(
                    v.replace("₺", "")
                    .replace("$", "")
                    .replace(",", "")
                    .replace("%", "")
                    .strip()
                )
            return float(v)

        s = temizle(suan)
        e = temizle(eski)
        if e == 0:
            return "0.00%"
        y = ((s - e) / e) * 100
        return f":{'green' if y>=0 else 'red'}[{y:+.2f}%]"
    except:
        return "0.00%"


def doviz_cek():
    try:
        res = requests.get("https://www.doviz.com/", timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        def t(sid):
            return float(
                soup.find("span", {"data-socket-key": sid})
                .text.strip()
                .replace(".", "")
                .replace(",", ".")
            )

        return {
            "USD": t("USD"),
            "EUR": t("EUR"),
            "GBP": t("GBP"),
            "gram-altin": t("gram-altin"),
        }
    except:
        return {"USD": gecmis_fiyatlar.get("USD_tl", 35.0)}


def kripto_fiyat_cek(kripto_sozlugu):
    ids = ",".join(kripto_sozlugu.keys())
    if not ids:
        return {}
    try:
        return requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd",
            timeout=5,
        ).json()
    except:
        return {}


def hisse_fiyat_cek(hisse_listesi):
    res = {}
    for h in hisse_listesi:
        try:
            t = yf.Ticker(h)
            hist = t.history(period="1d")
            f = hist["Close"].iloc[-1] if not hist.empty else 0
            if (h.upper() == "GMSTR.IS" and f < 100) or f <= 0:
                r = requests.get(
                    f"https://borsa.doviz.com/hisseler/{h.split('.')[0].lower()}",
                    timeout=5,
                )
                f = float(
                    BeautifulSoup(r.text, "html.parser")
                    .find("div", {"class": "text-xl font-semibold"})
                    .text.strip()
                    .replace(".", "")
                    .replace(",", ".")
                )
            res[h] = f
        except:
            res[h] = 0
    return res


# --- NAVİGASYON ---
st.sidebar.title("💳 Finans Merkezi")
sayfa = st.sidebar.radio(
    "Menü:", ["Ana Panel", "Geçmiş Performans", "Bütçe Yönetimi", "Bütçe Arşivi"]
)

# --- ANA PANEL ---
if sayfa == "Ana Panel":
    st.title("🚀 Varlık Kontrol Paneli")
    kurlar = doviz_cek()
    usd_try = kurlar.get("USD", 35.0)
    k_fiyatlar = kripto_fiyat_cek(veriler["kripto_paralar"])
    h_fiyatlar = hisse_fiyat_cek(veriler["hisseler"].keys())

    if "man_f" not in st.session_state:
        st.session_state.man_f = {}
    perf_data = []

    def ciz_tablo(kat, varliklar, kaynak, tip):
        liste = []
        t_tl = 0
        t_usd = 0
        t_e_tl = 0
        t_e_usd = 0
        for vid, data in varliklar.items():
            mik = data["miktar"]
            mal_usd = data["maliyet_usd"]
            man = st.session_state.man_f.get(f"m_{kat}_{vid}", 0)
            if tip == "kripto":
                f_usd = man if man > 0 else kaynak.get(vid, {}).get("usd", 0)
                if f_usd <= 0:
                    f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
                f_tl = f_usd * usd_try
            else:
                f_tl = (
                    man
                    if man > 0
                    else (
                        kaynak.get(vid, 0)
                        if tip == "hisse"
                        else kurlar.get(
                            {
                                "dolar": "USD",
                                "euro": "EUR",
                                "sterlin": "GBP",
                                "gram_altin": "gram-altin",
                            }.get(vid),
                            0,
                        )
                    )
                )
                if (vid.lower() == "gmstr.is" and f_tl < 100) or f_tl <= 0:
                    f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
                f_usd = f_tl / usd_try
            if mal_usd == 0:
                mal_usd = f_usd
            e_f_tl = gecmis_fiyatlar.get(f"{vid}_tl", f_tl)
            e_f_usd = gecmis_fiyatlar.get(f"{vid}_usd", f_usd)
            t_tl += mik * f_tl
            t_usd += mik * f_usd
            t_e_tl += mik * e_f_tl
            t_e_usd += mik * e_f_usd
            perf_data.append(
                {"Varlık": vid.upper(), "Maliyet ($)": mal_usd, "Mevcut ($)": f_usd}
            )
            liste.append(
                {
                    "Varlık": vid.upper(),
                    "Miktar": mik,
                    "Maliyet ($)": f"${mal_usd:,.2f}",
                    "Değer (TL)": f"₺{mik*f_tl:,.2f}",
                    "Değ (TL)": fmt_deg(f_tl, e_f_tl),
                    "Değer ($)": f"${mik*f_usd:,.2f}",
                    "Değ ($)": fmt_deg(f_usd, e_f_usd),
                }
            )
            gecmis_fiyatlar[f"{vid}_tl"] = f_tl
            gecmis_fiyatlar[f"{vid}_usd"] = f_usd
        st.subheader(kat.replace("_", " ").title())
        if liste:
            st.write(
                pd.DataFrame(liste).to_markdown(index=False), unsafe_allow_html=True
            )
            st.info(f"**Ara Toplam:** ₺{t_tl:,.2f} | ${t_usd:,.2f}")
        return {"tl": t_tl, "usd": t_usd, "e_tl": t_e_tl}

    res_k = ciz_tablo("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto")
    res_n = ciz_tablo("nakit_ve_emtia", veriler["nakit_ve_emtia"], None, "nakit")
    res_h = ciz_tablo("hisseler", veriler["hisseler"], h_fiyatlar, "hisse")

    g_tl = res_k["tl"] + res_n["tl"] + res_h["tl"]
    g_usd = res_k["usd"] + res_n["usd"] + res_h["usd"]
    e_tl = res_k["e_tl"] + res_n["e_tl"] + res_h["e_tl"]

    st.markdown("---")
    st.subheader("🎯 Maliyet Analizi")
    if perf_data:
        st.plotly_chart(
            px.bar(
                pd.DataFrame(perf_data),
                x="Varlık",
                y=["Maliyet ($)", "Mevcut ($)"],
                barmode="group",
            ),
            use_container_width=True,
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"₺{g_tl:,.2f}", fmt_deg(g_tl, e_tl))
    c2.metric("GENEL TOPLAM ($)", f"${g_usd:,.2f}")
    c3.metric("Dolar Kuru", f"₺{usd_try}")

    if st.button("💰 GÜNÜ KAPAT"):
        son_usd = g_usd
        if gecmis_kayitlar:
            try:
                val = gecmis_kayitlar[-1].get("Toplam ($)", str(g_usd))
                son_usd = float(val.replace("$", "").replace(",", "").strip())
            except:
                son_usd = g_usd

        kayit = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Kripto (TL)": f"₺{res_k['tl']:,.0f}",
            "Nakit (TL)": f"₺{res_n['tl']:,.0f}",
            "Borsa (TL)": f"₺{res_h['tl']:,.0f}",
            "Toplam (TL)": f"₺{g_tl:,.0f}",
            "Değişim (TL)": fmt_deg(g_tl, e_tl),
            "Toplam ($)": f"${g_usd:,.0f}",
            "Değişim ($)": fmt_deg(g_usd, son_usd),
            "Kripto ($)": f"${res_k['usd']:,.0f}",
            "Nakit ($)": f"${res_n['usd']:,.0f}",
            "Borsa ($)": f"${res_h['usd']:,.0f}",
        }
        gecmis_kayitlar.append(kayit)
        veri_kaydet("gecmis_arsiv.json", gecmis_kayitlar)
        st.success("Arşivlendi!")
        st.rerun()

# --- BÜTÇE YÖNETİMİ ---
elif sayfa == "Bütçe Yönetimi":
    st.title("📊 Bütçe")
    usd_val = doviz_cek().get("USD", 35.0)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Gelir")
        y_g = st.text_input("Gelir Adı Ekle")
        if st.button("Gelir Ekle"):
            if y_g:
                butce_verisi["gelirler"][y_g] = 0.0
                veri_kaydet("butce.json", butce_verisi)
                st.rerun()
        for k, v in butce_verisi["gelirler"].items():
            butce_verisi["gelirler"][k] = st.number_input(
                f"{k}", value=float(v), key=f"gel_{k}"
            )
        t_gel = sum(butce_verisi["gelirler"].values())
        st.success(f"Top: ₺{t_gel:,.2f}")
    with c2:
        st.subheader("Gider")

        def but_ciz(b, a):
            t = 0
            st.write(f"**{b}**")
            for n, v in butce_verisi["giderler"].get(a, {}).items():
                butce_verisi["giderler"][a][n] = st.number_input(
                    f"{n}", value=float(v), key=f"v_{a}_{n}"
                )
                t += butce_verisi["giderler"][a][n]
            return t

        t_gid = (
            but_ciz("Kartlar", "Kredi Kartlari")
            + but_ciz("Sabit", "Sabit Giderler")
            + but_ciz("Diğer", "Diger Borclar")
        )
        st.error(f"Top: ₺{t_gid:,.2f}")

    net = t_gel - t_gid
    st.header(f"Net: ₺{net:,.2f}")
    esk_net = net
    if butce_arsivi:
        try:
            val = butce_arsivi[-1].get("NET (TL)", net)
            if isinstance(val, str):
                val = val.replace("₺", "").replace(",", "").strip()
            esk_net = float(val)
        except:
            pass

    st.plotly_chart(
        px.bar(
            x=["Gelir", "Gider"],
            y=[t_gel, t_gid],
            color=["Gelir", "Gider"],
            color_discrete_map={"Gelir": "green", "Gider": "red"},
        ),
        use_container_width=True,
    )

    if st.button("💾 ARŞİVLE"):
        b_k = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "GELİR (TL)": f"₺{t_gel:,.0f}",
            "GİDER (TL)": f"₺{t_gid:,.0f}",
            "NET (TL)": f"₺{net:,.0f}",
            "NET ($)": f"${net/usd_val:,.0f}",
            "Değişim %": fmt_deg(net, esk_net),
        }
        butce_arsivi.append(b_k)
        veri_kaydet("butce_arsiv.json", butce_arsivi)
        st.success("Arşivlendi!")
        st.rerun()

elif sayfa == "Geçmiş Performans":
    st.title("📜 Arşiv")
    if not gecmis_kayitlar:
        st.info("Yok.")
    else:
        st.write(
            pd.DataFrame(gecmis_kayitlar[::-1]).to_markdown(index=False),
            unsafe_allow_html=True,
        )

elif sayfa == "Bütçe Arşivi":
    st.title("📜 Bütçe Arşivi")
    if not butce_arsivi:
        st.info("Yok.")
    else:
        st.write(
            pd.DataFrame(butce_arsivi[::-1]).to_markdown(index=False),
            unsafe_allow_html=True,
        )

with st.sidebar.expander("➕ Varlık & Akıllı Maliyet"):
    k = st.selectbox("Kategori", ["hisseler", "kripto_paralar", "nakit_ve_emtia"])
    c = st.text_input("Kod").lower()
    m = st.number_input("Miktar", value=0.0, format="%.8f")
    f = st.number_input("Alım Fiyatı ($)", value=0.0, format="%.4f")
    if st.button("Kaydet"):
        old = veriler[k].get(c, {"miktar": 0, "maliyet_usd": 0})
        old_m = old["miktar"]
        old_c = old["maliyet_usd"]
        new_c = (
            ((old_m * old_c) + ((m - old_m) * f)) / m
            if m > old_m and f > 0
            else (f if old_c == 0 else old_c)
        )
        veriler[k][c] = {"miktar": m, "maliyet_usd": new_c}
        veri_kaydet("varliklarim.json", veriler)
        st.rerun()
