import streamlit as st
import pandas as pd
import json
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import os
import html
from datetime import datetime
from email.utils import parsedate_to_datetime
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
            if dosya_adi == "butce.json":
                giderler = data.setdefault("giderler", {})
                kredi_kartlari = giderler.setdefault("Kredi Kartlari", {})
                aylik_sabit_gider_bilgi = data.setdefault("aylik_sabit_gider_bilgi", {})
                for kart_adi, kart_veri in list(kredi_kartlari.items()):
                    if isinstance(kart_veri, dict):
                        if "tutar" in kart_veri:
                            kredi_kartlari[kart_adi] = float(kart_veri.get("tutar", 0.0))
                        elif "kart_toplami" in kart_veri:
                            kredi_kartlari[kart_adi] = float(
                                kart_veri.get("kart_toplami", 0.0)
                            )
                        elif isinstance(kart_veri.get("duzenli_odemeler"), dict):
                            kredi_kartlari[kart_adi] = float(
                                sum(kart_veri["duzenli_odemeler"].values())
                            )
                        else:
                            kredi_kartlari[kart_adi] = 0.0
                    else:
                        kredi_kartlari[kart_adi] = float(kart_veri)
                for kalem, kayit in list(aylik_sabit_gider_bilgi.items()):
                    if isinstance(kayit, dict):
                        try:
                            tutar = float(kayit.get("tutar", 0.0))
                        except:
                            tutar = 0.0
                        bitis_tarihi = str(kayit.get("bitis_tarihi", "")).strip()
                    else:
                        try:
                            tutar = float(kayit)
                        except:
                            tutar = 0.0
                        bitis_tarihi = ""
                    aylik_sabit_gider_bilgi[kalem] = {
                        "tutar": tutar,
                        "bitis_tarihi": bitis_tarihi,
                    }
            return data
        except:
            return varsayilan


# Sayfa Ayarları
st.set_page_config(page_title="Finans Karargahı", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700;800&display=swap');
    .stApp {
        --ui-font-sm: 0.80rem;
        --ui-scale: 0.92;
        --bg-main: #07101c;
        --bg-panel: #0b1626;
        --bg-soft: #0f1d31;
        --line: #22324a;
        --text-main: #d9e1ec;
        --text-dim: #94a3b8;
        --up: #00d084;
        --down: #ff5f6d;
        --accent: #02c39a;
        font-family: 'Public Sans', sans-serif;
        background: radial-gradient(circle at 15% -10%, #11233b 0%, var(--bg-main) 40%);
        color: var(--text-main);
        font-size: calc(16px * var(--ui-scale));
    }
    .main .block-container {
        max-width: 1260px;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1321 0%, #0b1729 100%);
        border-right: 1px solid var(--line);
    }
    h1, h2, h3, h4 {
        letter-spacing: 0.2px;
        font-weight: 700;
        color: #e6edf7;
    }
    h1 { font-size: 2.05rem; }
    h2 { font-size: 1.6rem; }
    h3 { font-size: 1.25rem; }
    div[data-testid="stMarkdown"] p,
    div[data-testid="stMarkdown"] li,
    div[data-testid="stCaptionContainer"] {
        font-size: var(--ui-font-sm);
        color: var(--text-dim);
    }
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        min-height: 1.45rem;
        padding: 0 0.38rem;
        font-size: 0.76rem;
        border: 1px solid #2e4262;
        background: #102039;
        color: #dbe6f6;
    }
    div[data-testid="stButton"] > button[aria-label="−"] {
        color: #d85460;
        border: 1px solid #d85460;
        background: transparent;
        padding: 0 0.28rem;
        min-height: 1.45rem;
        line-height: 1;
    }
    div[data-testid="stButton"] > button[aria-label="−"]:hover {
        color: #ffffff;
        background: #e3342f;
        border-color: #e3342f;
    }
    div[data-testid="stTextInput"] > div,
    div[data-testid="stNumberInput"] > div,
    div[data-testid="stSelectbox"] > div {
        background: var(--bg-soft);
        border: 1px solid var(--line);
        border-radius: 8px;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        font-size: 0.78rem;
        min-height: 1.82rem;
        padding-top: 0.18rem;
        padding-bottom: 0.18rem;
        color: #dbe6f6;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label {
        font-size: 0.72rem;
        color: #9fb1cb;
    }
    div[data-testid="stMetric"] {
        background: #0d1a2d;
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 8px 10px;
    }
    .yf-table-wrap {
        overflow-x:auto;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #0a1627;
    }
    table.yf-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }
    table.yf-table th {
        background: #101f34;
        color: #c4d0e1;
        text-align: left;
        border-bottom: 1px solid var(--line);
        padding: 7px 7px;
        font-weight: 600;
    }
    table.yf-table td {
        border-top: 1px solid #1b2a40;
        padding: 6px 7px;
        color: #d9e1ec;
    }
    table.yf-table tr:hover td {
        background: #12233b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def parola_kontrol_ekrani():
    app_password = ""
    try:
        app_password = st.secrets.get("APP_PASSWORD", "")
    except:
        app_password = ""
    if not app_password:
        app_password = os.getenv("APP_PASSWORD", "")

    if not app_password:
        st.error(
            "Giriş şifresi ayarlı değil. Streamlit Secrets veya APP_PASSWORD env ayarla."
        )
        st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title("🔐 Güvenli Giriş")
    st.caption("Devam etmek için uygulama şifresini gir.")
    with st.form("login_form", clear_on_submit=False):
        girilen = st.text_input("Şifre", type="password")
        giris = st.form_submit_button("Giriş Yap")
        if giris:
            if girilen == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Şifre hatalı.")
    st.stop()


parola_kontrol_ekrani()

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
        "aylik_sabit_gider_bilgi": {},
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
    if isinstance(val, str):
        try:
            val = temizle_sayi(val)
        except:
            return ""
    if isinstance(val, (int, float)):
        color = "red" if val < 0 else "green" if val > 0 else "white"
        return f"color: {color}"
    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def gunluk_haber_maddeleri(sorgu):
    try:
        res = requests.get(
            "https://news.google.com/rss/search",
            params={
                "q": f"{sorgu} when:1d",
                "hl": "tr",
                "gl": "TR",
                "ceid": "TR:tr",
            },
            timeout=6,
        )
        soup = BeautifulSoup(res.content, "html.parser")
        items = []
        for item in soup.find_all("item")[:2]:
            baslik = item.title.text.strip() if item.title else ""
            kaynak = item.source.text.strip() if item.source else "Haber"
            tarih_raw = item.pubDate.text.strip() if item.pubDate else ""
            saat = ""
            if tarih_raw:
                try:
                    dt = parsedate_to_datetime(tarih_raw).astimezone()
                    saat = dt.strftime("%d.%m %H:%M")
                except:
                    saat = ""
            if baslik:
                items.append({"baslik": baslik, "kaynak": kaynak, "saat": saat})
        return items
    except:
        return []


def varlik_haber_sorgusu(vid, tip):
    if tip == "kripto":
        return f"{vid} kripto"
    if tip == "hisse":
        kod = vid.split(".")[0].upper()
        return f"{kod} BIST hisse" if ".is" in vid.lower() else f"{kod} stock"
    return {
        "dolar": "USDTRY döviz kuru",
        "euro": "EURTRY döviz kuru",
        "sterlin": "GBPTRY döviz kuru",
        "gram_altin": "gram altın",
    }.get(vid.lower(), vid)


def degisim_tooltip_olustur(vid, tip, deg_usd):
    yon = "yükseliş" if deg_usd >= 0 else "düşüş"
    sorgu = varlik_haber_sorgusu(vid, tip)
    haberler = gunluk_haber_maddeleri(sorgu)
    cumleler = [f"Son 24 saatte {vid.upper()} %{deg_usd:+.2f} ({yon}) hareket etti."]

    # Yahoo Finance: günlük + saatlik bağlam
    yf_symbol = None
    if tip == "hisse":
        yf_symbol = vid.upper()
    elif tip == "kripto":
        kmap = {
            "bitcoin": "BTC-USD",
            "ethereum": "ETH-USD",
            "solana": "SOL-USD",
            "ripple": "XRP-USD",
            "avalanche-2": "AVAX-USD",
            "optimism": "OP-USD",
            "arbitrum": "ARB-USD",
            "zksync": "ZK-USD",
            "eigenlayer": "EIGEN-USD",
        }
        yf_symbol = kmap.get(vid.lower())
    elif tip == "nakit":
        yf_symbol = {
            "dolar": "USDTRY=X",
            "euro": "EURTRY=X",
            "sterlin": "GBPTRY=X",
            "gram_altin": "XAUUSD=X",
        }.get(vid.lower())

    if yf_symbol:
        try:
            hist = yf.Ticker(yf_symbol).history(period="2d", interval="60m")
            if len(hist) > 2:
                son = float(hist["Close"].iloc[-1])
                onceki_saat = float(hist["Close"].iloc[-2])
                onceki_gun = float(hist["Close"].iloc[0])
                saatlik = ((son - onceki_saat) / onceki_saat * 100) if onceki_saat else 0.0
                gunluk = ((son - onceki_gun) / onceki_gun * 100) if onceki_gun else 0.0
                cumleler.append(
                    f"Yahoo Finance verisine göre saatlik %{saatlik:+.2f}, günlük %{gunluk:+.2f}."
                )
        except:
            pass

    # GLDTR / GMSTR için emtia endeks yorumu
    vid_upper = vid.upper()
    if vid_upper == "GLDTR.IS":
        try:
            emtia = yf.Ticker("XAUUSD=X").history(period="2d", interval="60m")
            if len(emtia) > 2:
                e_son = float(emtia["Close"].iloc[-1])
                e_gun = float(emtia["Close"].iloc[0])
                e_deg = ((e_son - e_gun) / e_gun * 100) if e_gun else 0.0
                cumleler.append(
                    f"GLDTR altın fiyatına endeksli; spot altında günlük %{e_deg:+.2f} hareket izlendi."
                )
        except:
            pass
    elif vid_upper == "GMSTR.IS":
        try:
            emtia = yf.Ticker("XAGUSD=X").history(period="2d", interval="60m")
            if len(emtia) > 2:
                e_son = float(emtia["Close"].iloc[-1])
                e_gun = float(emtia["Close"].iloc[0])
                e_deg = ((e_son - e_gun) / e_gun * 100) if e_gun else 0.0
                cumleler.append(
                    f"GMSTR gümüş fiyatına endeksli; spot gümüşte günlük %{e_deg:+.2f} hareket izlendi."
                )
        except:
            pass

    if not haberler:
        cumleler.append("Google News/TradingView tarafında belirgin yeni başlık yakalanamadı.")
        return " ".join(cumleler[:3])

    for h in haberler[:2]:
        zaman = f" ({h['saat']})" if h["saat"] else ""
        cumleler.append(f"{h['kaynak']}{zaman}: {h['baslik']}")
    return " ".join(cumleler[:3])


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

    def ciz_tablo(kat, varliklar, kaynak, tip):
        # BU KISIM ARTIK DOĞRU GİRİNTİLENMİŞ DURUMDA
        liste = []
        kod_liste = []
        t_tl, t_usd, t_e_tl, t_e_usd = 0, 0, 0, 0
        for vid, data in varliklar.items():
            mik, mal_usd = data["miktar"], data["maliyet_usd"]
            man = st.session_state.man_f.get(f"m_{kat}_{vid}", 0)

            # --- FİYAT HESAPLAMA MANTIĞI DÜZELTİLDİ ---
            if tip == "kripto":
                f_usd = man if man > 0 else kaynak.get(vid, {}).get("usd", 0)
                if f_usd <= 0:
                    f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
                f_tl = f_usd * usd_try
            
            elif tip == "hisse":
                raw_fiyat = man if man > 0 else kaynak.get(vid, 0)
                
                # EĞER HİSSE KODUNDA '.IS' YOKSA (AMZN, TSLA vb.) DOLAR BAZLIDIR
                if ".is" not in vid.lower() and man == 0:
                    f_usd = raw_fiyat
                    if f_usd <= 0: # Hata varsa geçmiş veriyi kullan
                        f_usd = gecmis_fiyatlar.get(f"{vid}_usd", 0)
                    f_tl = f_usd * usd_try
                else:
                    # TÜRK HİSSESİ (TL BAZLI)
                    f_tl = raw_fiyat
                    # GMSTR gibi özel durum kontrolü
                    if (vid.lower() == "gmstr.is" and f_tl < 100) or f_tl <= 0:
                        f_tl = gecmis_fiyatlar.get(f"{vid}_tl", 0)
                    f_usd = f_tl / usd_try

            else: # Nakit ve Emtia
                f_tl = (
                    man
                    if man > 0
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
                f_usd = f_tl / usd_try
            # ------------------------------------------

            kz_yuzde = ((f_usd - mal_usd) / mal_usd * 100) if mal_usd > 0 else 0
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
                    "Değ% (TL)": fmt_yuzde(
                        f_tl, gecmis_fiyatlar.get(f"{vid}_tl", f_tl)
                    ),
                    "Değer ($)": mik * f_usd,
                    "Değ% ($)": fmt_yuzde(
                        f_usd, gecmis_fiyatlar.get(f"{vid}_usd", f_usd)
                    ),
                }
            )
            kod_liste.append(vid)
            gecmis_fiyatlar[f"{vid}_tl"], gecmis_fiyatlar[f"{vid}_usd"] = f_tl, f_usd

        st.subheader(kat.replace("_", " ").title())
        if liste:
            df = pd.DataFrame(liste)
            cols = [
                "Varlık",
                "Miktar",
                "Maliyet ($)",
                "Birim Fiyat ($)",
                "K/Z %",
                "Değer (TL)",
                "Değ% (TL)",
                "Değer ($)",
                "Değ% ($)",
            ]
            html_rows = []
            for i, row in df.iterrows():
                ozet = degisim_tooltip_olustur(kod_liste[i], tip, float(row["Değ% ($)"]))
                tooltip = html.escape(ozet, quote=True)

                def cfmt(col, val):
                    if col in ["Maliyet ($)", "Birim Fiyat ($)", "Değer ($)"]:
                        return f"${float(val):,.2f}"
                    if col == "Değer (TL)":
                        return f"₺{float(val):,.2f}"
                    if col in ["K/Z %", "Değ% (TL)"]:
                        renk = "#ff5f6d" if float(val) < 0 else ("#00d084" if float(val) > 0 else "#cbd5e1")
                        return f"<span style='color:{renk}'>{float(val):+.2f}%</span>"
                    if col == "Değ% ($)":
                        renk = "#ff5f6d" if float(val) < 0 else ("#00d084" if float(val) > 0 else "#cbd5e1")
                        return (
                            f"<span title=\"{tooltip}\" style='color:{renk}; cursor:help;'>"
                            f"{float(val):+.2f}%</span>"
                        )
                    if col == "Miktar":
                        return f"{float(val):,.6f}"
                    return str(val)

                tds = "".join([f"<td>{cfmt(c, row[c])}</td>" for c in cols])
                html_rows.append(f"<tr>{tds}</tr>")

            thead = "".join([f"<th>{c}</th>" for c in cols])
            table_html = (
                "<div class='yf-table-wrap'>"
                "<table class='yf-table'>"
                f"<thead><tr>{thead}</tr></thead>"
                f"<tbody>{''.join(html_rows)}</tbody>"
                "</table></div>"
            )
            st.markdown(table_html, unsafe_allow_html=True)
            st.info(f"**Ara Toplam:** ₺{t_tl:,.2f} | ${t_usd:,.2f}")
        return {"tl": t_tl, "usd": t_usd, "e_tl": t_e_tl, "e_usd": t_e_usd}

    res_k = ciz_tablo("kripto_paralar", veriler["kripto_paralar"], k_fiyatlar, "kripto")
    res_n = ciz_tablo("nakit_ve_emtia", veriler["nakit_ve_emtia"], None, "nakit")
    res_h = ciz_tablo("hisseler", veriler["hisseler"], h_fiyatlar, "hisse")

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

    gumus_deger_tl = 0
    altin_deger_tl = 0

    for sembol, data in veriler["hisseler"].items():
        s_upper = sembol.upper()
        miktar = data["miktar"]
        fiyat = gecmis_fiyatlar.get(f"{sembol}_tl", 0)

        if "GMSTR" in s_upper:
            gumus_deger_tl = miktar * fiyat
        elif "GLDTR" in s_upper:
            altin_deger_tl = miktar * fiyat

    riskli_hisse_degeri = max(0, res_h["tl"] - (gumus_deger_tl + altin_deger_tl))
    guvenli_liman_degeri = res_n["tl"] + gumus_deger_tl + altin_deger_tl
    yuksek_risk_kripto_degeri = res_k["tl"]

    toplam_servet = (
        riskli_hisse_degeri + guvenli_liman_degeri + yuksek_risk_kripto_degeri
    )
    if toplam_servet <= 0:
        toplam_servet = 1

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

    if m_oranlar["Yüksek Risk (Kripto)"] > 40:
        st.warning(
            "👉 Kripto ağırlığın hedeflediğin %30'un üzerinde. Kar realize etmeyi düşünebilirsin."
        )
    elif m_oranlar["Hisse (Şirket Riskli)"] < 15:
        st.info(
            "👉 Şirket hissesi ağırlığın düşük kalmış. Uzun vadeli büyüme için ekleme yapabilirsin."
        )

    st.markdown("### 📈 Maliyet/Değer Performansı (Kâr/Zarar)")
    kat_maliyetler = {}
    toplam_maliyet_usd = 0
    kategoriler = {
        "Kripto Paralar": veriler["kripto_paralar"],
        "Nakit ve Emtia": veriler["nakit_ve_emtia"],
        "Hisseler": veriler["hisseler"],
    }

    for ad, varlik_listesi in kategoriler.items():
        m = sum(v["miktar"] * v["maliyet_usd"] for v in varlik_listesi.values())
        kat_maliyetler[ad] = m
        toplam_maliyet_usd += m

    m1, m2, m3, m4 = st.columns(4)

    def kz_metrik_yaz(col, baslik, guncel_usd, maliyet_usd):
        oran = (
            ((guncel_usd - maliyet_usd) / maliyet_usd * 100) if maliyet_usd > 0 else 0
        )
        col.metric(baslik, f"{oran:+.2f}%", help=f"Toplam Maliyet: ${maliyet_usd:,.2f}")

    kz_metrik_yaz(m1, "Kripto Paralar", res_k["usd"], kat_maliyetler["Kripto Paralar"])
    kz_metrik_yaz(m2, "Nakit ve Emtia", res_n["usd"], kat_maliyetler["Nakit ve Emtia"])
    kz_metrik_yaz(m3, "Hisseler", res_h["usd"], kat_maliyetler["Hisseler"])
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

# --- DİĞER SAYFALAR (GEÇMİŞ, BÜTÇE VS.) ---
elif sayfa == "Geçmiş Performans":
    st.title("📜 Arşiv")
    if not gecmis_kayitlar:
        st.info("Yok.")
    else:
        df_a = pd.DataFrame(gecmis_kayitlar)
        df_a["Toplam_TL_Num"] = df_a["Toplam (TL)"].apply(temizle_sayi)
        df_a["Toplam_USD_Num"] = df_a["Toplam ($)"].apply(temizle_sayi)

        onceki_tl = df_a["Toplam_TL_Num"].shift(1)
        onceki_usd = df_a["Toplam_USD_Num"].shift(1)

        df_a["Deg_TL_Hesap"] = np.where(
            onceki_tl.abs() > 0,
            ((df_a["Toplam_TL_Num"] - onceki_tl) / onceki_tl.abs()) * 100,
            0.0,
        )
        df_a["Deg_USD_Hesap"] = np.where(
            onceki_usd.abs() > 0,
            ((df_a["Toplam_USD_Num"] - onceki_usd) / onceki_usd.abs()) * 100,
            0.0,
        )

        df_a["Değişim (TL)"] = df_a["Deg_TL_Hesap"].apply(lambda x: f"{x:+.2f}%")
        df_a["Değişim ($)"] = df_a["Deg_USD_Hesap"].apply(lambda x: f"{x:+.2f}%")

        gosterim_df = df_a.iloc[::-1].drop(
            columns=["Toplam_TL_Num", "Toplam_USD_Num", "Deg_TL_Hesap", "Deg_USD_Hesap"]
        )
        st.dataframe(
            gosterim_df.style.applymap(renk_stili, subset=["Değişim (TL)", "Değişim ($)"]),
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
        for k in list(butce_verisi["gelirler"].keys()):
            c_del, c_val = st.columns([0.2, 1.8])
            with c_del:
                if st.button("−", key=f"sil_gel_{k}", help="Kalemi sil"):
                    del butce_verisi["gelirler"][k]
                    github_a_kaydet("butce.json", butce_verisi)
                    st.rerun()
            with c_val:
                butce_verisi["gelirler"][k] = st.number_input(
                    f"{k}", value=float(butce_verisi["gelirler"][k]), key=f"gel_{k}"
                )
        t_gel = sum(butce_verisi["gelirler"].values())
        st.success(f"Top: ₺{t_gel:,.2f}")

        st.markdown("---")
        st.subheader("Aylık Sabit Giderler (Bilgi Amaçlı)")
        st.caption("Bu bölüm genel gelir-gider hesabına dahil edilmez.")
        if "aylik_sabit_gider_bilgi" not in butce_verisi:
            butce_verisi["aylik_sabit_gider_bilgi"] = {}

        c_kalem, c_tutar, c_tarih = st.columns([2, 1, 1])
        with c_kalem:
            yeni_sabit_kalem = st.text_input(
                "Harcama Kalemi",
                key="yeni_sabit_kalem",
                placeholder="Örn: İnternet",
            )
        with c_tutar:
            yeni_sabit_tutar = st.number_input(
                "Tutar",
                min_value=0.0,
                value=0.0,
                key="yeni_sabit_tutar",
            )
        with c_tarih:
            yeni_sabit_bitis = st.text_input(
                "Son Bulma Tarihi (YYYY-MM-DD)",
                key="yeni_sabit_bitis",
                placeholder="Örn: 2026-12-31",
            )
        if (
            st.button("Sabit Gider Ekle/Güncelle", key="sabit_gider_ekle_btn")
            and yeni_sabit_kalem
        ):
            bitis_tarihi = yeni_sabit_bitis.strip()
            if bitis_tarihi:
                try:
                    datetime.strptime(bitis_tarihi, "%Y-%m-%d")
                except:
                    st.error("Son bulma tarihi formatı hatalı. YYYY-MM-DD gir.")
                    bitis_tarihi = ""
            butce_verisi["aylik_sabit_gider_bilgi"][yeni_sabit_kalem] = {
                "tutar": float(yeni_sabit_tutar),
                "bitis_tarihi": bitis_tarihi,
            }
            github_a_kaydet("butce.json", butce_verisi)
            st.success(f"{yeni_sabit_kalem} listeye eklendi/güncellendi.")

        bilgi_toplam = 0.0
        st.markdown("**Sil** | **Harcama Kalemi** | **Tutar (₺)** | **Son Bulma Tarihi**")
        sirali_kalemler = sorted(
            butce_verisi["aylik_sabit_gider_bilgi"].items(),
            key=lambda kv: float(
                kv[1].get("tutar", 0.0) if isinstance(kv[1], dict) else kv[1]
            ),
            reverse=True,
        )
        for kalem, kayit in sirali_kalemler:
            if not isinstance(kayit, dict):
                kayit = {"tutar": float(kayit), "bitis_tarihi": ""}
                butce_verisi["aylik_sabit_gider_bilgi"][kalem] = kayit
            c_del, c_item, c_val, c_end = st.columns([0.2, 2.05, 0.95, 1.25])
            with c_del:
                if st.button("−", key=f"sil_bilgi_{kalem}", help="Kalemi sil"):
                    del butce_verisi["aylik_sabit_gider_bilgi"][kalem]
                    github_a_kaydet("butce.json", butce_verisi)
                    st.rerun()
            with c_item:
                st.text_input(
                    "Kalem",
                    value=kalem,
                    disabled=True,
                    key=f"bilgi_kalem_{kalem}",
                    label_visibility="collapsed",
                )
            with c_val:
                val = st.number_input(
                    "Tutar",
                    min_value=0.0,
                    value=float(kayit.get("tutar", 0.0)),
                    key=f"bilgi_tutar_{kalem}",
                    label_visibility="collapsed",
                )
            with c_end:
                end_date = st.text_input(
                    "Son Bulma Tarihi",
                    value=str(kayit.get("bitis_tarihi", "")),
                    key=f"bilgi_bitis_{kalem}",
                    label_visibility="collapsed",
                    placeholder="YYYY-MM-DD",
                ).strip()
            butce_verisi["aylik_sabit_gider_bilgi"][kalem] = {
                "tutar": float(val),
                "bitis_tarihi": end_date,
            }
            bilgi_toplam += float(val)
        st.info(f"Aylık Sabit Giderler Toplamı (Bilgi): ₺{bilgi_toplam:,.2f}")

        gelecek_12_ay = []
        simdi = datetime.now()
        for i in range(12):
            yil = simdi.year + ((simdi.month - 1 + i) // 12)
            ay = ((simdi.month - 1 + i) % 12) + 1
            referans = datetime(yil, ay, 15)
            ay_toplam = 0.0

            for kayit in butce_verisi["aylik_sabit_gider_bilgi"].values():
                if not isinstance(kayit, dict):
                    continue
                tutar = float(kayit.get("tutar", 0.0))
                bitis_tarihi = str(kayit.get("bitis_tarihi", "")).strip()
                aktif = True
                if bitis_tarihi:
                    try:
                        bitis = datetime.strptime(bitis_tarihi, "%Y-%m-%d")
                        if bitis < referans:
                            aktif = False
                    except:
                        aktif = True
                if aktif:
                    ay_toplam += tutar

            gelecek_12_ay.append(
                {"Ay": referans.strftime("%Y-%m"), "Aylık Sabit Gider (₺)": ay_toplam}
            )

        df_12 = pd.DataFrame(gelecek_12_ay)
    with c2:
        st.subheader("Gider")
        st.write("**Yeni Gider Kalemi Ekle/Güncelle**")
        g1, g2, g3 = st.columns([1, 2, 1])
        with g1:
            gider_kat = st.selectbox(
                "Kategori",
                ["Kredi Kartlari", "Sabit Giderler", "Diger Borclar"],
                format_func=lambda x: {
                    "Kredi Kartlari": "Kartlar",
                    "Sabit Giderler": "Sabit",
                    "Diger Borclar": "Diğer",
                }[x],
                key="gider_kat_sec",
            )
        with g2:
            yeni_gider_adi = st.text_input(
                "Gider Kalemi", key="yeni_gider_adi", placeholder="Örn: Netflix"
            )
        with g3:
            yeni_gider_tutar = st.number_input(
                "Tutar (₺)", min_value=0.0, value=0.0, key="yeni_gider_tutar"
            )
        if st.button("Gider Ekle/Güncelle", key="gider_ekle_btn") and yeni_gider_adi:
            butce_verisi["giderler"].setdefault(gider_kat, {})
            butce_verisi["giderler"][gider_kat][yeni_gider_adi] = float(yeni_gider_tutar)
            github_a_kaydet("butce.json", butce_verisi)
            st.success(f"{yeni_gider_adi} eklendi/güncellendi.")
            st.rerun()

        def but_ciz(b, a):
            t = 0
            st.write(f"**{b}**")
            for n in list(butce_verisi["giderler"].get(a, {}).keys()):
                c_del, c_val = st.columns([0.2, 1.8])
                with c_del:
                    if st.button("−", key=f"sil_{a}_{n}", help="Kalemi sil"):
                        del butce_verisi["giderler"][a][n]
                        github_a_kaydet("butce.json", butce_verisi)
                        st.rerun()
                v = butce_verisi["giderler"][a][n]
                if isinstance(v, dict):
                    v = float(
                        v.get(
                            "kart_toplami",
                            v.get("tutar", sum(v.get("duzenli_odemeler", {}).values())),
                        )
                    )
                with c_val:
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
    st.markdown(
        f"<p style='font-size:24px;font-weight:700;margin:0 0 8px 0;'>Net: ₺{net:,.2f}</p>",
        unsafe_allow_html=True,
    )
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        fig_gel_gider = px.bar(
            x=["Gelir", "Gider"],
            y=[t_gel, t_gid],
            color=["Gelir", "Gider"],
            color_discrete_map={"Gelir": "green", "Gider": "red"},
            title="Gelir / Gider",
        )
        fig_gel_gider.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_gel_gider, use_container_width=True)
    with g_col2:
        fig_12 = px.bar(
            df_12,
            x="Ay",
            y="Aylık Sabit Gider (₺)",
            title="Önümüzdeki 12 Ay Sabit Gider (15'i)",
        )
        fig_12.update_layout(
            xaxis_title="Ay",
            yaxis_title="Tutar (₺)",
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_12, use_container_width=True)
    if st.button("💾 ARŞİVLE"):
        github_a_kaydet("butce.json", butce_verisi)
        net_usd = net / usd_val if usd_val else 0.0
        onceki_net_usd = None
        if butce_arsivi:
            try:
                onceki_net_usd = temizle_sayi(butce_arsivi[-1].get("NET ($)", 0))
            except:
                onceki_net_usd = None
        if onceki_net_usd is None or onceki_net_usd == 0:
            degisim_yuzde = 0.0
        else:
            degisim_yuzde = ((net_usd - onceki_net_usd) / abs(onceki_net_usd)) * 100

        b_k = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "GELİR (TL)": f"₺{t_gel:,.0f}",
            "GİDER (TL)": f"₺{t_gid:,.0f}",
            "NET (TL)": f"₺{net:,.0f}",
            "NET ($)": f"${net_usd:,.0f}",
            "Değişim %": f"{degisim_yuzde:+.2f}%",
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
        df_ba = pd.DataFrame(butce_arsivi[::-1])
        st.dataframe(
            df_ba.style.applymap(renk_stili, subset=["NET (TL)", "NET ($)", "Değişim %"]),
            use_container_width=True,
        )

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
