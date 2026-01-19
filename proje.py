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
                st.error(
                    f"GitHub Hatası ({dosya_adi}): {put_res.json().get('message')}"
                )
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
            if dosya_adi == "varliklarim.json":
                for kat in data:
                    for vid in data[kat]:
                        if not isinstance(data[kat][vid], dict):
                            data[kat][vid] = {
                                "miktar": data[kat][vid],
                                "maliyet_usd": 0.0,
                            }
            return data
        except:
            return varsayilan


# Sayfa Ayarları
st.set_page_config(page_title="Finans Karargahı", layout="wide")

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
def temizle_sayi(v):
    if isinstance(v, str):
        return float(
            v.replace("₺", "")
            .replace("$", "")
            .replace(",", "")
            .replace("%", "")
            .strip()
        )
    return float(v)


def fmt_yuzde(suan, eski):
    try:
        s, e = temizle_sayi(suan), temizle_sayi(eski)
        return ((s - e) / e) * 100 if e != 0 else 0.0
    except:
        return 0.0


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
            val = (
                soup.find("span", {"data-socket-key": sid})
                .text.strip()
                .replace(".", "")
                .replace(",", ".")
            )
            return float(val)

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
            t_obj = yf.Ticker(h)
            hist = t_obj.history(period="1d")
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


# --- MODÜLER HESAPLAMA VE GÖSTERİM ---


def hesapla_varlik_verileri(kat, varliklar, kaynak, tip, usd_try):
    """Sadece matematiksel hesaplamaları yapar."""
    liste = []
    t_tl, t_usd, t_e_tl, t_e_usd = 0, 0, 0, 0

    for vid, data in varliklar.items():
        mik, mal_usd = data["miktar"], data["maliyet_usd"]

        # Fiyat Belirleme Mantığı
        if tip == "kripto":
            f_usd = kaynak.get(vid, {}).get("usd", 0)
            if f_usd <= 0:
                f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
            f_tl = f_usd * usd_try
        else:
            f_tl = (
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
            if f_tl <= 0:
                f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
            f_usd = f_tl / usd_try if usd_try > 0 else 0

        kz_yuzde = ((f_usd - mal_usd) / mal_usd * 100) if mal_usd > 0 else 0

        # Toplamlar
        t_tl += mik * f_tl
        t_usd += mik * f_usd
        t_e_tl += mik * gecmis_fiyatlar.get(f"{vid}_tl", f_tl)
        t_e_usd += mik * gecmis_fiyatlar.get(f"{vid}_usd", f_usd)

        liste.append(
            {
                "Varlık": vid.upper(),
                "Miktar": mik,
                "Maliyet ($)": mal_usd,
                "Birim Fiyat ($)": f_usd,
                "K/Z %": kz_yuzde,
                "Değer (TL)": mik * f_tl,
                "Değ% (TL)": fmt_yuzde(f_tl, gecmis_fiyatlar.get(f"{vid}_tl", f_tl)),
                "Değer ($)": mik * f_usd,
                "Değ% ($)": fmt_yuzde(f_usd, gecmis_fiyatlar.get(f"{vid}_usd", f_usd)),
            }
        )
        # Geçmiş fiyat güncelleme (Side effect ama gerekli)
        gecmis_fiyatlar[f"{vid}_tl"], gecmis_fiyatlar[f"{vid}_usd"] = f_tl, f_usd

    return liste, {"tl": t_tl, "usd": t_usd, "e_tl": t_e_tl, "e_usd": t_e_usd}


def tablo_goster(baslik, veri_listesi, toplamlar):
    """Sadece görselleştirme yapar."""
    st.subheader(baslik)
    if veri_listesi:
        df = pd.DataFrame(veri_listesi)
        st.dataframe(
            df.style.format(
                {
                    "Maliyet ($)": "${:,.2f}",
                    "Birim Fiyat ($)": "${:,.2f}",
                    "K/Z %": "{:+.2f}%",
                    "Değer (TL)": "₺{:,.2f}",
                    "Değer ($)": "${:,.2f}",
                    "Değ% (TL)": "{:+.2f}%",
                    "Değ% ($)": "{:+.2f}%",
                }
            ).applymap(renk_stili, subset=["K/Z %", "Değ% (TL)", "Değ% ($)"]),
            use_container_width=True,
        )
        st.info(f"**Ara Toplam:** ₺{toplamlar['tl']:,.2f} | ${toplamlar['usd']:,.2f}")


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

    # Verileri Hesapla
    list_k, res_k = hesapla_varlik_verileri(
        "kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto", usd_try
    )
    list_n, res_n = hesapla_varlik_verileri(
        "nakit_ve_emtia", veriler["nakit_ve_emtia"], kurlar, "nakit", usd_try
    )
    list_h, res_h = hesapla_varlik_verileri(
        "hisseler", veriler["hisseler"], h_fiyatlar, "hisse", usd_try
    )

    # Tabloları Göster
    tablo_goster("Kripto Paralar", list_k, res_k)
    tablo_goster("Nakit ve Emtia", list_n, res_n)
    tablo_goster("Hisseler", list_h, res_h)

    g_tl = res_k["tl"] + res_n["tl"] + res_h["tl"]
    g_usd = res_k["usd"] + res_n["usd"] + res_h["usd"]
    e_tl = res_k["e_tl"] + res_n["e_tl"] + res_h["e_tl"]
    e_usd = res_k["e_usd"] + res_n["e_usd"] + res_h["e_usd"]

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("GENEL TOPLAM (TL)", f"₺{g_tl:,.2f}", f"{fmt_yuzde(g_tl, e_tl):+.2f}%")
    c2.metric("GENEL TOPLAM ($)", f"${g_usd:,.2f}", f"{fmt_yuzde(g_usd, e_usd):+.2f}%")
    c3.metric("Dolar Kuru", f"₺{usd_try}")

    # --- RİSK VE DAĞILIM ANALİZİ ---
    st.markdown("### ⚖️ Portföy Risk ve Dağılım Analizi")
    gumus_deger_tl = sum(
        d["Miktar"] * gecmis_fiyatlar.get(f"{d['Varlık'].lower()}_tl", 0)
        for d in list_h
        if "GMSTR" in d["Varlık"]
    )
    altin_deger_tl = sum(
        d["Miktar"] * gecmis_fiyatlar.get(f"{d['Varlık'].lower()}_tl", 0)
        for d in list_h
        if "GLDTR" in d["Varlık"]
    )

    riskli_hisse_degeri = max(0, res_h["tl"] - (gumus_deger_tl + altin_deger_tl))
    guvenli_liman_degeri = res_n["tl"] + gumus_deger_tl + altin_deger_tl
    yuksek_risk_kripto_degeri = res_k["tl"]

    toplam_servet = max(
        1, riskli_hisse_degeri + guvenli_liman_degeri + yuksek_risk_kripto_degeri
    )

    m_oranlar = {
        "Hisse (Şirket Riskli)": (riskli_hisse_degeri / toplam_servet) * 100,
        "Güvenli Liman (Altın/Gümüş/Nakit)": (guvenli_liman_degeri / toplam_servet)
        * 100,
        "Yüksek Risk (Kripto)": (yuksek_risk_kripto_degeri / toplam_servet) * 100,
    }

    ideal_oranlar = {
        "Hisse (Şirket Riskli)": 25.0,
        "Güvenli Liman (Altın/Gümüş/Nakit)": 45.0,
        "Yüksek Risk (Kripto)": 30.0,
    }
    analiz_df = []
    for anahtar in m_oranlar.keys():
        fark = m_oranlar[anahtar] - ideal_oranlar[anahtar]
        durum = (
            "✅ Dengeli" if abs(fark) < 5 else ("⚠️ Fazla" if fark > 0 else "📉 Eksik")
        )
        analiz_df.append(
            {
                "Varlık Sınıfı": anahtar,
                "Mevcut Oran": f"%{m_oranlar[anahtar]:.1f}",
                "İdeal Oran": f"%{ideal_oranlar[anahtar]:.1f}",
                "Fark": f"{fark:+.1f}%",
                "Durum": durum,
            }
        )

    st.table(pd.DataFrame(analiz_df))

    st.markdown("### 📈 Maliyet/Değer Performansı (Kâr/Zarar)")
    kat_maliyetler = {
        "Kripto": sum(
            v["miktar"] * v["maliyet_usd"] for v in veriler["kripto_paralar"].values()
        ),
        "Nakit": sum(
            v["miktar"] * v["maliyet_usd"] for v in veriler["nakit_ve_emtia"].values()
        ),
        "Hisse": sum(
            v["miktar"] * v["maliyet_usd"] for v in veriler["hisseler"].values()
        ),
    }
    toplam_maliyet_usd = sum(kat_maliyetler.values())

    m1, m2, m3, m4 = st.columns(4)

    def kz_metrik_yaz(col, baslik, guncel_usd, maliyet_usd):
        oran = (
            ((guncel_usd - maliyet_usd) / maliyet_usd * 100) if maliyet_usd > 0 else 0
        )
        col.metric(baslik, f"{oran:+.2f}%", help=f"Toplam Maliyet: ${maliyet_usd:,.2f}")

    kz_metrik_yaz(m1, "Kripto Paralar", res_k["usd"], kat_maliyetler["Kripto"])
    kz_metrik_yaz(m2, "Nakit ve Emtia", res_n["usd"], kat_maliyetler["Nakit"])
    kz_metrik_yaz(m3, "Hisseler", res_h["usd"], kat_maliyetler["Hisse"])
    kz_metrik_yaz(m4, "TÜM VARLIKLAR", g_usd, toplam_maliyet_usd)

    if st.button("💰 GÜNÜ KAPAT"):
        kayit = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Kripto (TL)": f"₺{res_k['tl']:,.0f}",
            "Nakit (TL)": f"₺{res_n['tl']:,.0f}",
            "Borsa (TL)": f"₺{res_h['tl']:,.0f}",
            "Toplam (TL)": f"₺{g_tl:,.0f}",
            "Değişim (TL)": f"{fmt_yuzde(g_tl, e_tl):+.2f}%",
            "Kripto ($)": f"${res_k['usd']:,.0f}",
            "Nakit ($)": f"${res_n['usd']:,.0f}",
            "Borsa ($)": f"${res_h['usd']:,.0f}",
            "Toplam ($)": f"${g_usd:,.0f}",
            "Değişim ($)": f"{fmt_yuzde(g_usd, e_usd):+.2f}%",
        }
        gecmis_kayitlar.append(kayit)
        github_a_kaydet("gecmis_arsiv.json", gecmis_kayitlar)
        github_a_kaydet("fiyat_gecmis.json", gecmis_fiyatlar)
        st.success("GitHub'a arşivlendi!")
        st.rerun()

# --- DİĞER SAYFALAR ---
elif sayfa == "Geçmiş Performans":
    st.title("📜 Arşiv")
    if not gecmis_kayitlar:
        st.info("Yok.")
    else:
        df_a = pd.DataFrame(gecmis_kayitlar[::-1])
        df_a["Deg_TL_Num"] = df_a["Değişim (TL)"].apply(
            lambda x: float(str(x).replace("%", "")) if x else 0
        )
        df_a["Deg_USD_Num"] = df_a["Değişim ($)"].apply(
            lambda x: float(str(x).replace("%", "")) if x else 0
        )
        st.dataframe(
            df_a.style.applymap(renk_stili, subset=["Deg_TL_Num", "Deg_USD_Num"]),
            use_container_width=True,
        )

elif sayfa == "Bütçe Yönetimi":
    st.title("📊 Bütçe")
    usd_val = doviz_cek().get("USD", 35.0)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Gelir")
        y_g = st.text_input("Gelir Ekle")
        if st.button("Ekle", key="gelir_btn") and y_g:
            butce_verisi["gelirler"][y_g] = 0.0
            github_a_kaydet("butce.json", butce_verisi)
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
            "Değişim %": "0.00%",
        }
        butce_arsivi.append(b_k)
        github_a_kaydet("butce_arsiv.json", butce_arsivi)
        st.success("Arşivlendi!")
        st.rerun()

elif sayfa == "Bütçe Arşivi":
    st.title("📜 Bütçe Arşivi")
    if not butce_arsivi:
        st.info("Yok.")
    else:
        st.dataframe(pd.DataFrame(butce_arsivi[::-1]), use_container_width=True)

# SIDEBAR VARLIK EKLEME
with st.sidebar.expander("➕ Varlık Yönetimi & Maliyet"):
    kat_sec = st.selectbox("Kategori", ["hisseler", "kripto_paralar", "nakit_ve_emtia"])
    kod_sec = st.text_input("Kod (Örn: btc, thyao.is)").lower().strip()
    mik_sec = st.number_input("Yeni Toplam Miktar", value=0.0, format="%.8f")
    fiy_sec = st.number_input("Son Alım Fiyatı ($)", value=0.0, format="%.4f")

    col1, col2 = st.columns(2)
    if col1.button("Kaydet/Güncelle"):
        if kod_sec:
            old = veriler[kat_sec].get(kod_sec, {"miktar": 0, "maliyet_usd": 0})
            new_c = (
                (
                    (old["miktar"] * old["maliyet_usd"])
                    + ((mik_sec - old["miktar"]) * fiy_sec)
                )
                / mik_sec
                if mik_sec > old["miktar"] and fiy_sec > 0
                else (old["maliyet_usd"] if fiy_sec == 0 else fiy_sec)
            )
            veriler[kat_sec][kod_sec] = {"miktar": mik_sec, "maliyet_usd": new_c}
            github_a_kaydet("varliklarim.json", veriler)
            st.success(f"{kod_sec} güncellendi.")
            st.rerun()

    if col2.button("Varlığı Sil"):
        if kod_sec in veriler[kat_sec]:
            del veriler[kat_sec][kod_sec]
            github_a_kaydet("varliklarim.json", veriler)
            st.warning(f"{kod_sec} silindi.")
            st.rerun()
