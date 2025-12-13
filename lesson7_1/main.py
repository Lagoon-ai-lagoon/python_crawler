import asyncio
import json
import streamlit as st
from datetime import datetime, timedelta
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import pandas as pd
from typing import Optional, Dict, List

# 配置 Streamlit 頁面
st.set_page_config(
    page_title="台幣匯率轉換",
    page_icon="💱",
    layout="wide"
)

st.title("💱 台幣匯率轉換系統")

# ==================== 爬蟲相關函數 ====================

async def fetch_exchange_rates() -> Optional[List[Dict]]:
    """
    使用 crawl4ai 爬取銀行匯率資料
    """
    schema = {
        "name": "匯率資訊",
        "baseSelector": "table[title='牌告匯率'] tr",
        "fields": [
            {
                "name": "幣別",
                "selector": "td[data-table='幣別'] div.print_show",
                "type": "text"
            },
            {
                "name": "本行即期買入",
                "selector": "td[data-table='本行即期買入']",
                "type": "text"
            },
            {
                "name": "本行即期賣出",
                "selector": "td[data-table='本行即期賣出']",
                "type": "text"
            }
        ]
    }

    strategy = JsonCssExtractionStrategy(schema)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=strategy
    )
    
    async with AsyncWebCrawler() as crawler:
        url = 'https://rate.bot.com.tw/xrt?Lang=zh-TW'
        result = await crawler.arun(url=url, config=run_config)
        
        if result.extracted_content:
            data = json.loads(result.extracted_content)
            # 提取 extracted_data 中的 data 字段
            if isinstance(data, dict) and 'extracted_data' in data:
                rates_list = data['extracted_data'].get('data', [])
            else:
                rates_list = data if isinstance(data, list) else []
            
            return rates_list
        return None


def clean_rate_data(rates: List[Dict]) -> pd.DataFrame:
    """
    清理和驗證匯率資料
    - 移除「暫停交易」的貨幣
    - 設定空字段為「暫停交易」
    - 返回 DataFrame
    """
    if not rates:
        return pd.DataFrame()
    
    cleaned_data = []
    
    for rate in rates:
        currency = rate.get('幣別', '').strip()
        buy_rate = rate.get('本行即期買入', '').strip()
        sell_rate = rate.get('本行即期賣出', '').strip()
        
        # 跳過無效記錄
        if not currency:
            continue
            
        # 檢查是否為「暫停交易」
        if "暫停交易" in buy_rate or "暫停交易" in sell_rate:
            continue
        
        # 設定空字段為「暫停交易」
        if not buy_rate:
            buy_rate = "暫停交易"
        if not sell_rate:
            sell_rate = "暫停交易"
        
        try:
            # 嘗試轉換為浮點數以驗證有效性
            buy_float = float(buy_rate) if buy_rate != "暫停交易" else None
            sell_float = float(sell_rate) if sell_rate != "暫停交易" else None
            
            # 至少有一個交易率可用才納入
            if buy_float is not None or sell_float is not None:
                cleaned_data.append({
                    '幣別': currency,
                    '買入': buy_rate,
                    '賣出': sell_rate,
                    '買入值': buy_float,
                    '賣出值': sell_float
                })
        except ValueError:
            continue
    
    return pd.DataFrame(cleaned_data) if cleaned_data else pd.DataFrame()


def save_rates_to_cache(df: pd.DataFrame):
    """將匯率資料儲存到 session state"""
    st.session_state.rates_cache = df
    st.session_state.last_update = datetime.now()


# ==================== Streamlit 界面 ====================

# 初始化 session state
if 'rates_cache' not in st.session_state:
    st.session_state.rates_cache = None
    st.session_state.last_update = None

# 創建頂部控制欄
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    st.markdown("**上次更新時間:**")
    if st.session_state.last_update:
        st.text(st.session_state.last_update.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        st.text("尚未更新")

with col2:
    st.markdown("**更新頻率:** 每 10 分鐘自動刷新")

with col3:
    if st.button("🔄 手動更新", key="manual_refresh"):
        st.session_state.need_refresh = True

# 決定是否需要更新資料
need_update = False

if st.session_state.rates_cache is None:
    need_update = True
elif st.session_state.last_update:
    time_diff = datetime.now() - st.session_state.last_update
    if time_diff >= timedelta(minutes=10):
        need_update = True

# 執行更新
if need_update or st.session_state.get('need_refresh', False):
    with st.spinner("📡 正在更新匯率資料..."):
        try:
            # 執行非同步爬蟲
            rates_data = asyncio.run(fetch_exchange_rates())
            
            if rates_data:
                rates_df = clean_rate_data(rates_data)
                if not rates_df.empty:
                    save_rates_to_cache(rates_df)
                    st.success("✅ 匯率資料更新成功！")
                else:
                    st.warning("⚠️ 無有效的匯率資料")
            else:
                st.error("❌ 無法取得匯率資料，請稍後重試")
        except Exception as e:
            st.error(f"❌ 更新失敗: {str(e)}")
    
    if 'need_refresh' in st.session_state:
        st.session_state.need_refresh = False

# 主要內容區域
if st.session_state.rates_cache is not None and not st.session_state.rates_cache.empty:
    # 創建兩欄版面
    left_col, right_col = st.columns([1, 1])
    
    # ==================== 左欄：匯率計算機 ====================
    with left_col:
        st.subheader("💰 匯率計算機")
        
        # 台幣輸入
        twd_amount = st.number_input(
            "輸入台幣金額 (TWD)",
            min_value=0.0,
            step=100.0,
            value=1000.0
        )
        
        # 選擇目標貨幣
        rates_df = st.session_state.rates_cache.copy()
        currencies = rates_df[rates_df['買入值'].notna()]['幣別'].tolist()
        
        if currencies:
            selected_currency = st.selectbox("選擇目標貨幣", currencies)
            
            # 取得選定貨幣的賣出率（將台幣轉換為外幣時使用賣出率）
            currency_row = rates_df[rates_df['幣別'] == selected_currency]
            
            if not currency_row.empty:
                sell_rate = currency_row.iloc[0]['賣出值']
                
                if sell_rate and sell_rate != "暫停交易":
                    converted_amount = twd_amount / float(sell_rate)
                    
                    # 顯示計算結果
                    st.success(f"✅ 轉換結果")
                    st.metric(
                        label=f"TWD → {selected_currency}",
                        value=f"{converted_amount:.2f}",
                        delta=f"匯率: {sell_rate}"
                    )
                    
                    # 詳細資訊
                    st.info(
                        f"💡 計算公式：\n"
                        f"{twd_amount:.2f} TWD ÷ {sell_rate} = {converted_amount:.2f} {selected_currency}"
                    )
                else:
                    st.warning(f"⚠️ {selected_currency} 暫停交易")
        else:
            st.warning("⚠️ 目前無可交易的貨幣")
    
    # ==================== 右欄：匯率表格 ====================
    with right_col:
        st.subheader("📊 匯率表格")
        
        # 準備展示用的 DataFrame
        display_df = st.session_state.rates_cache[['幣別', '買入', '賣出']].copy()
        
        # 換列名稱便於展示
        display_df = display_df.rename(columns={
            '幣別': '幣別',
            '買入': '本行即期買入',
            '賣出': '本行即期賣出'
        })
        
        # 顯示表格
        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            height=400
        )
        
        # 統計資訊
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("可交易幣別數", len(display_df))
        
        with col2:
            active_currencies = len(display_df[display_df['本行即期買入'] != '暫停交易'])
            st.metric("活躍幣別", active_currencies)
        
        with col3:
            st.metric("暫停交易", len(display_df[display_df['本行即期買入'] == '暫停交易']))

else:
    st.info("📡 正在載入匯率資料，請稍候...")
    with st.spinner("初始化應用..."):
        try:
            rates_data = asyncio.run(fetch_exchange_rates())
            if rates_data:
                rates_df = clean_rate_data(rates_data)
                if not rates_df.empty:
                    save_rates_to_cache(rates_df)
        except Exception as e:
            st.error(f"初始化失敗: {str(e)}")

# 頁腳
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>"
    f"<small>資料來源: 中央銀行 | 最後更新: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S') if st.session_state.last_update else '尚未更新'}</small>"
    "</div>",
    unsafe_allow_html=True
)


streamlit run main.py --server.port 8501