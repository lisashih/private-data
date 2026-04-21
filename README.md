# 口袋證券廣告成效儀表板

Streamlit 廣告成效儀表板，支援 META / ASA / Google KW / Google PMax 四平台。

## 功能

- 📊 **四平台整合**：META / ASA / Google KW / Google PMax
- 🔄 **自動 join 轉換**：進件數/完開數從獨立分頁 join 到廣告活動層級
- 📅 **週 WoW & 月累計**：自動計算本週/上週對比
- 💰 **預算進度條**：輸入實際花費即時更新
- 📈 **視覺化圖表**：Plotly 互動式圖表

## xlsx 格式

| 分頁 | 說明 |
|------|------|
| META | 天數, 行銷活動名稱, 曝光次數, 連結點擊次數, 花費金額 (TWD) |
| ASA | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 下載數, 花費（台幣） |
| Google KW | Date, 廣告活動, 廣告群組, 廣告關鍵字, 曝光, 點擊, 花費 |
| Google Pmax | Date, 廣告活動, 曝光, 點擊, 花費 |
| **進件數完開數** | Date, 平台, 廣告活動, 進件數, 完開數 ← 手填轉換資料 |

> ⚠️ **進件數/完開數** 在關鍵字層級無法匹配，只在廣告活動層級有效。
> 請在「進件數完開數」分頁填入後上傳，系統會自動 join。

## 本地執行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 部署

1. 將此資料夾 push 到 GitHub repo
2. 前往 [share.streamlit.io](https://share.streamlit.io)
3. New app → 選擇 repo → Main file: `app.py`
4. Deploy！

## 檔案結構

```
ad-dashboard/
├── app.py               # 主程式
├── data_processor.py    # 資料處理模組
├── requirements.txt     # Python 相依套件
├── .streamlit/
│   └── config.toml      # 主題設定
└── README.md
```
