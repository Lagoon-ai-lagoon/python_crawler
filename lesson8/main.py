"""
台灣銀行匯率查詢系統 - tkinter 桌面應用程式

整合 crawl4ai 爬蟲與 tkinter GUI 框架
- 即時爬取台灣銀行牌告匯率
- 表格化顯示匯率資訊
- 台幣轉換計算器（雙向計算）
- 手動更新機制
- 無障礙設計（適合老年使用者）
"""

import asyncio
import json
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from datetime import datetime
from typing import Optional, List, Dict

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy


# ============= 爬蟲模組 =============

async def fetch_exchange_rates() -> Optional[List[Dict[str, str]]]:
    """
    爬取台灣銀行匯率資訊
    
    功能：
    - 訪問台灣銀行官方網站
    - 使用 JsonCssExtractionStrategy 提取結構化資料
    - 自動清理空白字元與無效資料
    - 返回可用的匯率列表
    
    Returns:
        List[Dict[str, str]]: 匯率資料列表，每項包含：
            - 幣別: 貨幣代碼 (e.g., USD, JPY)
            - 本行即期買入: 買入匯率
            - 本行即期賣出: 賣出匯率
        如果爬蟲失敗返回 None
    
    Raises:
        Exception: 爬蟲過程中的任何錯誤
    """
    try:
        # 定義 CSS 提取策略（參考 lesson8_1.py）
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
        
        extraction_strategy = JsonCssExtractionStrategy(schema)
        
        # 爬取資料
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url="https://rate.bot.com.tw/xrt?Lang=zh-TW",
                config=CrawlerRunConfig(
                    extraction_strategy=extraction_strategy,
                    cache_mode=CacheMode.BYPASS,
                )
            )
            
            # 解析結果
            if result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    rates = data if isinstance(data, list) else data.get("data", [])
                    
                    # 清理資料：去除空白、過濾無效資料
                    cleaned_rates = []
                    for rate in rates:
                        if not isinstance(rate, dict):
                            continue
                        
                        currency_full = str(rate.get("幣別", "")).strip()
                        buy = str(rate.get("本行即期買入", "")).strip()
                        sell = str(rate.get("本行即期賣出", "")).strip()
                        
                        # 跳過暫停交易的貨幣（買入和賣出都是 "-"）
                        if buy == "-" and sell == "-":
                            continue
                        
                        # 從「美金 (USD)」提取「USD」
                        currency_code = currency_full
                        if "(" in currency_full and ")" in currency_full:
                            currency_code = currency_full.split("(")[1].split(")")[0]
                        
                        if currency_code and buy and sell and buy != "-" and sell != "-":
                            cleaned_rates.append({
                                "幣別": currency_code,
                                "本行即期買入": buy,
                                "本行即期賣出": sell,
                            })
                    
                    print(f"成功爬取 {len(cleaned_rates)} 筆匯率資料")
                    return cleaned_rates if cleaned_rates else None
                except json.JSONDecodeError as e:
                    print(f"JSON 解析失敗: {e}")
                    print(f"原始內容: {result.extracted_content[:200]}")
                    return None
        
        return None
        
    except Exception as e:
        print(f"爬蟲錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============= GUI 應用程式 =============

class ExchangeRateApp(tk.Tk):
    """
    匯率查詢應用程式主視窗
    
    使用 tkinter Grid 布局建立三區塊設計：
    - 頂部：標題欄 (更新按鈕 + 狀態 + 時間)
    - 左側：匯率表格 (Treeview)
    - 右側：台幣轉換計算器
    """
    
    def __init__(self):
        """初始化應用程式"""
        super().__init__()
        
        # 設定視窗屬性
        self.title("🏦 台灣銀行匯率查詢系統")
        self.geometry("1200x750")
        self.resizable(True, True)
        self.config(bg="#f0f0f0")
        
        # 應用程式狀態
        self.exchange_data: Optional[List[Dict[str, str]]] = None
        self.last_update: Optional[datetime] = None
        self.is_loading = False
        
        # 建立 UI
        self._setup_ui()
        
        # 載入初始資料
        self._load_initial_data()
    
    def _setup_ui(self):
        """建立 UI 元件與布局"""
        
        # 配置列權重 (可拖動調整視窗大小)
        self.columnconfigure(0, weight=1, minsize=600)
        self.columnconfigure(1, weight=1, minsize=400)
        self.rowconfigure(1, weight=1)
        
        # ===== 頂部標題欄 =====
        title_frame = tk.Frame(self, bg="white", relief=tk.RAISED, bd=1)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)
        title_frame.columnconfigure(1, weight=1)
        
        # 標題
        title_label = tk.Label(
            title_frame,
            text="🏦 台灣銀行匯率查詢系統",
            font=("Arial", 24, "bold"),
            bg="white",
            fg="#2c3e50"
        )
        title_label.grid(row=0, column=0, padx=15, pady=15)
        
        # 更新按鈕
        self.update_btn = tk.Button(
            title_frame,
            text="🔄 更新匯率",
            font=("Arial", 16, "bold"),
            bg="#3498db",
            fg="white",
            padx=15,
            pady=10,
            command=self._fetch_data_thread,
            cursor="hand2"
        )
        self.update_btn.grid(row=0, column=1, padx=10, pady=15)
        
        # 狀態標籤
        self.status_label = tk.Label(
            title_frame,
            text="",
            font=("Arial", 14),
            bg="white",
            fg="#3498db"
        )
        self.status_label.grid(row=0, column=2, padx=10, pady=15)
        
        # 時間標籤
        self.time_label = tk.Label(
            title_frame,
            text="最後更新: -",
            font=("Arial", 14),
            bg="white",
            fg="#7f8c8d"
        )
        self.time_label.grid(row=0, column=3, padx=15, pady=15)
        
        # ===== 左側 - 匯率表格 =====
        left_frame = tk.Frame(self, bg="#ecf0f1", relief=tk.RAISED, bd=1)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=10)
        left_frame.rowconfigure(1, weight=1)
        left_frame.columnconfigure(0, weight=1)
        
        # 左側標題
        left_title = tk.Label(
            left_frame,
            text="📊 匯率資訊",
            font=("Arial", 18, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        left_title.grid(row=0, column=0, sticky="w", padx=15, pady=15)
        
        # Treeview 表格
        tree_columns = ("幣別", "本行即期買入", "本行即期賣出")
        self.tree = ttk.Treeview(
            left_frame,
            columns=tree_columns,
            height=15,
            show="headings"
        )
        
        # 設定欄位
        self.tree.column("幣別", width=200)
        self.tree.column("本行即期買入", width=160)
        self.tree.column("本行即期賣出", width=160)
        
        self.tree.heading("幣別", text="幣別")
        self.tree.heading("本行即期買入", text="本行即期買入")
        self.tree.heading("本行即期賣出", text="本行即期賣出")
        
        # 設定字體與行高
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Arial", 16, "bold"))
        style.configure("Treeview", font=("Arial", 14), rowheight=35)
        
        self.tree.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # 捲軸
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 15), pady=(0, 15))
        self.tree.configure(yscroll=scrollbar.set)
        
        # ===== 右側 - 台幣轉換計算器 =====
        right_frame = tk.Frame(self, bg="#e8f4f8", relief=tk.RAISED, bd=1)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=8, pady=10)
        right_frame.columnconfigure(0, weight=1)
        
        # 右側標題
        right_title = tk.Label(
            right_frame,
            text="💱 台幣轉換計算器",
            font=("Arial", 18, "bold"),
            bg="#e8f4f8",
            fg="#2c3e50"
        )
        right_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=15)
        
        # 台幣金額輸入
        twd_label = tk.Label(
            right_frame,
            text="💵 台幣金額:",
            font=("Arial", 16),
            bg="#e8f4f8",
            fg="#2c3e50"
        )
        twd_label.grid(row=1, column=0, sticky="w", padx=20, pady=10)
        
        self.twd_entry = tk.Entry(right_frame, font=("Arial", 16), width=20)
        self.twd_entry.grid(row=1, column=1, sticky="w", padx=20, pady=10)
        self.twd_entry.insert(0, "1000")
        
        # 貨幣選擇
        currency_label = tk.Label(
            right_frame,
            text="🌍 目標貨幣:",
            font=("Arial", 16),
            bg="#e8f4f8",
            fg="#2c3e50"
        )
        currency_label.grid(row=2, column=0, sticky="w", padx=20, pady=10)
        
        self.currency_combo = ttk.Combobox(
            right_frame,
            font=("Arial", 16),
            width=15,
            state="readonly"
        )
        self.currency_combo.grid(row=2, column=1, sticky="w", padx=20, pady=10)
        
        # 計算按鈕
        calc_btn = tk.Button(
            right_frame,
            text="💱 計算轉換",
            font=("Arial", 16, "bold"),
            bg="#27ae60",
            fg="white",
            padx=20,
            pady=10,
            command=self._calculate_conversion,
            cursor="hand2"
        )
        calc_btn.grid(row=3, column=0, columnspan=2, pady=25)
        
        # 結果顯示
        result_title = tk.Label(
            right_frame,
            text="📊 轉換結果",
            font=("Arial", 14, "bold"),
            bg="#e8f4f8",
            fg="#2c3e50"
        )
        result_title.grid(row=4, column=0, columnspan=2, sticky="w", padx=20, pady=(15, 5))
        
        self.result_label = tk.Label(
            right_frame,
            text="請先選擇貨幣並點擊計算",
            font=("Arial", 14),
            bg="white",
            fg="#7f8c8d",
            justify=tk.LEFT,
            relief=tk.SUNKEN,
            bd=1,
            wraplength=300
        )
        self.result_label.grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=20,
            pady=15
        )
        
        # 配置右側框架的行權重，讓結果區自動擴展
        right_frame.rowconfigure(5, weight=1)
    
    def _load_initial_data(self):
        """應用程式啟動時載入初始資料"""
        self._fetch_data_thread()
    
    def _fetch_data_thread(self):
        """
        在背景執行緒中爬取資料
        
        流程：
        1. 檢查是否正在載入中
        2. 顯示載入狀態
        3. 啟動背景執行緒執行非同步爬蟲
        4. 完成後更新 UI
        """
        if self.is_loading:
            messagebox.showinfo("提示", "正在載入中，請稍候...")
            return
        
        self.is_loading = True
        self._show_loading()
        
        def run_async():
            """在新的事件迴圈中執行非同步函數"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                data = loop.run_until_complete(fetch_exchange_rates())
                # 使用 after 確保在主執行緒中更新 UI
                self.after(0, lambda: self._update_ui_with_data(data))
            except Exception as e:
                self.after(
                    0,
                    lambda: self._show_error(f"爬蟲失敗: {str(e)}")
                )
            finally:
                loop.close()
                self.is_loading = False
        
        # 啟動背景執行緒
        thread = Thread(target=run_async, daemon=True)
        thread.start()
    
    def _show_loading(self):
        """顯示載入狀態"""
        self.status_label.config(text="⏳ 載入中...", foreground="#3498db")
        self.update_btn.config(state="disabled")
        self.config(cursor="watch")
    
    def _hide_loading(self):
        """隱藏載入狀態"""
        self.status_label.config(text="")
        self.update_btn.config(state="normal")
        self.config(cursor="")
    
    def _show_error(self, message: str):
        """顯示錯誤訊息"""
        self._hide_loading()
        self.is_loading = False
        messagebox.showerror("錯誤", message)
    
    def _update_ui_with_data(self, data: Optional[List[Dict[str, str]]]):
        """
        更新 UI 資料
        
        功能：
        1. 隱藏載入狀態
        2. 驗證資料有效性
        3. 更新 Treeview 表格
        4. 更新下拉選單（智能過濾）
        5. 更新時間戳
        6. 顯示成功訊息
        """
        self._hide_loading()
        
        if data is None or len(data) == 0:
            self.is_loading = False
            messagebox.showerror("錯誤", "無法取得匯率資料，請稍後重試")
            return
        
        # 儲存資料與時間
        self.exchange_data = data
        self.last_update = datetime.now()
        
        # 更新表格
        self._update_treeview()
        
        # 更新下拉選單
        self._update_currency_combo()
        
        # 更新時間標籤
        self.time_label.config(
            text=f"最後更新: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 顯示成功訊息（3秒後消失）
        self.status_label.config(text="✅ 更新成功", foreground="#27ae60")
        self.after(3000, lambda: self.status_label.config(text=""))
        
        self.is_loading = False
    
    def _update_treeview(self):
        """更新 Treeview 表格"""
        # 清空舊資料
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 插入新資料
        if self.exchange_data:
            for rate in self.exchange_data:
                currency = rate.get("幣別", "")
                buy = rate.get("本行即期買入", "暫停交易")
                sell = rate.get("本行即期賣出", "暫停交易")
                
                self.tree.insert("", tk.END, values=(currency, buy, sell))
    
    def _update_currency_combo(self):
        """
        更新下拉選單（智能過濾不可交易的貨幣）
        
        過濾條件：
        - 必須同時有買入和賣出匯率
        - 排除空值或「暫停交易」
        """
        available_currencies = []
        
        if self.exchange_data:
            for rate in self.exchange_data:
                currency = rate.get("幣別", "").strip()
                buy = rate.get("本行即期買入", "").strip()
                sell = rate.get("本行即期賣出", "").strip()
                
                # 只加入可交易的貨幣
                if currency and buy and sell:
                    available_currencies.append(currency)
        
        self.currency_combo['values'] = available_currencies
        if available_currencies:
            self.currency_combo.current(0)
    
    def _find_rate_by_currency(self, currency: str) -> Optional[Dict[str, str]]:
        """
        根據貨幣代碼查找匯率資料
        
        Args:
            currency: 貨幣代碼 (e.g., "USD")
        
        Returns:
            Dict[str, str]: 包含買入和賣出匯率的字典
        """
        if not self.exchange_data:
            return None
        
        for rate in self.exchange_data:
            if rate.get("幣別") == currency:
                return rate
        
        return None
    
    def _calculate_conversion(self):
        """
        計算台幣轉換
        
        流程：
        1. 驗證輸入台幣金額（>0）
        2. 驗證已選擇目標貨幣
        3. 查找該貨幣的匯率
        4. 使用買入/賣出匯率分別計算
        5. 格式化並顯示結果
        """
        try:
            # 驗證輸入金額
            twd_amount_str = self.twd_entry.get().strip()
            if not twd_amount_str:
                messagebox.showwarning("警告", "請輸入台幣金額")
                return
            
            twd_amount = float(twd_amount_str)
            if twd_amount <= 0:
                messagebox.showwarning("警告", "金額必須大於 0")
                return
            
            # 驗證選擇貨幣
            selected_currency = self.currency_combo.get()
            if not selected_currency:
                messagebox.showwarning("警告", "請選擇目標貨幣")
                return
            
            # 查找匯率
            rate_data = self._find_rate_by_currency(selected_currency)
            if not rate_data:
                messagebox.showerror("錯誤", f"無法找到 {selected_currency} 的匯率")
                return
            
            # 取得匯率值
            buy_rate = float(rate_data["本行即期買入"])
            sell_rate = float(rate_data["本行即期賣出"])
            
            # 計算轉換結果
            buy_result = twd_amount / buy_rate
            sell_result = twd_amount / sell_rate
            
            # 格式化結果
            result_text = (
                f"═══════════════════════════\n"
                f"💰 轉換金額: {twd_amount:,.2f} 台幣\n"
                f"🌍 目標貨幣: {selected_currency}\n"
                f"═══════════════════════════\n\n"
                f"📤 銀行買入匯率\n"
                f"   匯率: {buy_rate}\n"
                f"   您可得: {buy_result:.2f} {selected_currency}\n\n"
                f"📥 銀行賣出匯率\n"
                f"   匯率: {sell_rate}\n"
                f"   您需付: {sell_result:.2f} {selected_currency}\n\n"
                f"═══════════════════════════\n"
                f"計算時間: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # 顯示結果
            self.result_label.config(text=result_text, fg="#2c3e50")
            
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的金額（數字）")
        except Exception as e:
            messagebox.showerror("錯誤", f"計算失敗: {str(e)}")


# ============= 主程式入口 =============

def main():
    """應用程式入口"""
    app = ExchangeRateApp()
    app.mainloop()


if __name__ == "__main__":
    main()
