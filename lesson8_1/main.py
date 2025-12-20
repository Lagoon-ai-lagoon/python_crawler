"""
股票即時監控桌面應用程式

使用 Tkinter 建立 GUI，結合 crawl4ai 爬蟲技術，
提供台灣股市即時資訊監控功能。

Author: Created on 2025-12-20
"""

import asyncio
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, List, Optional, Set
from datetime import datetime
import threading
import queue
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import twstock


# ==================== 爬蟲模組 ====================

def get_stock_schema() -> Dict:
    """
    取得股票資訊的 CSS 提取 Schema
    
    Returns:
        股票資訊的 Schema 定義
    """
    return {
        "name": "StockInfo",
        "baseSelector": "main.main",
        "fields": [
            {
                "name": "日期時間",
                "selector": "time.last-time#lastQuoteTime",
                "type": "text"
            },
            {
                "name": "股票號碼",
                "selector": "span.astock-code[c-model='id']",
                "type": "text"
            },
            {
                "name": "股票名稱",
                "selector": "h3.astock-name[c-model='name']",
                "type": "text"
            },
            {
                "name": "即時價格",
                "selector": "div.quotes-info div.deal",
                "type": "text"
            },
            {
                "name": "漲跌",
                "selector": "div.quotes-info span.chg[c-model='change']",
                "type": "text"
            },
            {
                "name": "漲跌百分比",
                "selector": "div.quotes-info span.chg-rate[c-model='changeRate']",
                "type": "text"
            },
            {
                "name": "開盤價",
                "selector": "div.quotes-info #quotesUl span[c-model-dazzle='text:open,class:openUpDn']",
                "type": "text"
            },
            
            {
                "name": "最高價",
                "selector": "div.quotes-info #quotesUl span[c-model-dazzle='text:high,class:highUpDn']",
                "type": "text"
            },
            {
                "name": "成交量(張)",
                "selector": "div.quotes-info #quotesUl span[c-model='volume']",
                "type": "text"
            },
            {
                "name": "最低價",
                "selector": "div.quotes-info #quotesUl span[c-model-dazzle='text:low,class:lowUpDn']",
                "type": "text"
            },
            {
                "name": "前一日收盤價",
                "selector": "div.quotes-info #quotesUl span[c-model='previousClose']",
                "type": "text"
            }
        ]
    }


async def fetch_single_stock(
    crawler: AsyncWebCrawler,
    stock_code: str,
    base_config: CrawlerRunConfig,
    semaphore: asyncio.Semaphore
) -> Optional[Dict]:
    """
    抓取單一股票資訊
    
    Args:
        crawler: AsyncWebCrawler 實例
        stock_code: 股票代碼
        base_config: 基礎爬蟲執行設定
        semaphore: 用於限制並行數量的信號量
    
    Returns:
        股票資訊字典，失敗時返回 None
    """
    async with semaphore:
        url = f'https://www.wantgoo.com/stock/{stock_code}/technical-chart'
        
        try:
            # 針對每個股票創建帶有等待條件的配置
            config = CrawlerRunConfig(
                cache_mode=base_config.cache_mode,
                extraction_strategy=base_config.extraction_strategy,
                scan_full_page=base_config.scan_full_page,
                verbose=base_config.verbose,
                # 等待關鍵元素載入完成
                wait_for="js:() => document.querySelector('div.quotes-info div.deal') && document.querySelector('span.astock-code[c-model=\"id\"]') && document.querySelector('#quotesUl span[c-model=\"volume\"]')",
                wait_for_timeout=15000,
                page_timeout=30000
            )
            
            result = await crawler.arun(url=url, config=config)
            
            if result.success and result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    if data and len(data) > 0:
                        stock_data = data[0]
                        stock_data['stock_code'] = stock_code
                        stock_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        return stock_data
                except json.JSONDecodeError:
                    print(f"✗ 股票 {stock_code} JSON 解析失敗")
                    return None
            else:
                print(f"✗ 股票 {stock_code} 下載失敗")
                return None
                
        except Exception as e:
            print(f"✗ 股票 {stock_code} 發生錯誤: {e}")
            return None


async def fetch_multiple_stocks(stock_codes: List[str]) -> List[Dict]:
    """
    批次並行爬取多支股票資訊
    
    Args:
        stock_codes: 股票代碼列表
    
    Returns:
        成功爬取的股票資訊列表
    """
    stock_schema = get_stock_schema()
    extraction_strategy = JsonCssExtractionStrategy(schema=stock_schema)
    
    browser_config = BrowserConfig(headless=True)
    
    base_crawler_run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
        scan_full_page=True,
        verbose=False
    )
    
    # 限制同時爬取數量
    semaphore = asyncio.Semaphore(3)
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [
            fetch_single_stock(crawler, code, base_crawler_run_config, semaphore)
            for code in stock_codes
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 過濾成功的結果
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"發生異常: {result}")
            elif result is not None:
                successful_results.append(result)
        
        return successful_results


def run_crawler_in_thread(stock_codes: List[str], result_queue: queue.Queue):
    """
    在背景執行緒中執行爬蟲任務
    
    Args:
        stock_codes: 要爬取的股票代碼列表
        result_queue: 用於傳遞結果的佇列
    """
    try:
        # 在執行緒中建立新的事件迴圈
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(fetch_multiple_stocks(stock_codes))
        result_queue.put(('success', results))
        
        loop.close()
    except Exception as e:
        result_queue.put(('error', str(e)))


# ==================== GUI 主程式 ====================

class StockMonitorApp:
    """股票監控應用程式主類別"""
    
    def __init__(self, root: tk.Tk):
        """
        初始化應用程式
        
        Args:
            root: Tkinter 根視窗
        """
        self.root = root
        self.root.title("台灣股市即時監控系統")
        self.root.geometry("1200x700")
        
        # 觀察清單（使用 Set 避免重複）
        self.watchlist: Set[str] = set()
        
        # 股票資料快取
        self.stock_data_cache: Dict[str, Dict] = {}
        
        # 自動更新相關
        self.auto_update_enabled = False
        self.update_timer_id = None
        self.is_updating = False
        
        # 爬蟲結果佇列
        self.result_queue = queue.Queue()
        
        # 建立 UI
        self.setup_ui()
        
        # 載入台灣股票清單
        self.load_tw_stocks()
        
        # 綁定視窗關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 開始檢查佇列
        self.check_queue()
    
    def setup_ui(self):
        """建立使用者介面"""
        # TODO: Phase 3 - 實作 UI 佈局
        
        # 主要容器 - 使用 PanedWindow 分割左右面板
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左側面板 - 股票選擇區
        self.setup_left_panel(main_paned)
        
        # 右側面板 - 資料顯示區
        self.setup_right_panel(main_paned)
        
        # 頂部工具列
        self.setup_toolbar()
    
    def setup_toolbar(self):
        """建立頂部工具列"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # 手動更新按鈕
        self.update_btn = ttk.Button(
            toolbar,
            text="🔄 手動更新",
            command=self.manual_update,
            state=tk.NORMAL
        )
        self.update_btn.pack(side=tk.LEFT, padx=5)
        
        # 自動更新開關
        self.auto_update_var = tk.BooleanVar(value=False)
        auto_update_check = ttk.Checkbutton(
            toolbar,
            text="自動更新 (每分鐘)",
            variable=self.auto_update_var,
            command=self.toggle_auto_update
        )
        auto_update_check.pack(side=tk.LEFT, padx=5)
        
        # 狀態標籤
        self.status_label = ttk.Label(toolbar, text="就緒")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # 最後更新時間
        self.last_update_label = ttk.Label(toolbar, text="")
        self.last_update_label.pack(side=tk.RIGHT, padx=5)
    
    def setup_left_panel(self, parent):
        """建立左側股票選擇面板"""
        left_frame = tk.Frame(parent, bg='#f5f5f5')
        parent.add(left_frame, weight=1)
        
        # === 標題區域 ===
        title_frame = tk.Frame(left_frame, bg='#2c3e50', height=50)
        title_frame.pack(fill=tk.X, padx=0, pady=0)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📈 台灣股票清單",
            font=('Arial', 16, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=12)
        
        # === 搜尋框區域 ===
        search_frame = tk.Frame(left_frame, bg='#f5f5f5')
        search_frame.pack(fill=tk.X, padx=15, pady=15)
        
        search_label = tk.Label(
            search_frame,
            text="🔍 搜尋股票",
            font=('Arial', 11),
            bg='#f5f5f5',
            fg='#333333'
        )
        search_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Arial', 12),
            bg='white',
            fg='#333333',
            relief=tk.SOLID,
            bd=1
        )
        search_entry.pack(fill=tk.X, ipady=8)
        
        # === 股票列表區域 ===
        list_label_frame = tk.Frame(left_frame, bg='#f5f5f5')
        list_label_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        list_label = tk.Label(
            list_label_frame,
            text="📊 選擇股票 (雙擊加入)",
            font=('Arial', 11),
            bg='#f5f5f5',
            fg='#333333'
        )
        list_label.pack(anchor=tk.W)
        
        # 列表框框架
        list_frame = tk.Frame(left_frame, bg='white', relief=tk.SOLID, bd=1, height=320)
        list_frame.pack(fill=tk.BOTH, padx=15, pady=(0, 15))
        list_frame.pack_propagate(False)
        
        # 滾動條
        scrollbar = tk.Scrollbar(list_frame, bg='#e0e0e0', activebackground='#cccccc')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 股票列表 - 優化視覺
        self.stock_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=('Arial', 12),
            bg='white',
            fg='#333333',
            relief=tk.FLAT,
            bd=0,
            selectmode=tk.SINGLE,
            selectbackground='#3498db',
            selectforeground='white',
            activestyle='none',
            height=10,
            highlightthickness=0
        )
        self.stock_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.stock_listbox.yview)
        
        # 雙擊加入觀察
        self.stock_listbox.bind('<Double-Button-1>', self.on_stock_double_click)
        
        # === 底部按鈕區域 ===
        button_frame = tk.Frame(left_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X, padx=15, pady=10)
        
        add_btn = tk.Button(
            button_frame,
            text="➕ 加入觀察清單",
            command=self.add_to_watchlist,
            font=('Arial', 12, 'bold'),
            bg='#27ae60',
            fg='white',
            relief=tk.FLAT,
            padx=15,
            pady=10,
            cursor='hand2',
            activebackground='#229954',
            activeforeground='white'
        )
        add_btn.pack(fill=tk.X)
    
    def setup_right_panel(self, parent):
        """建立右側資料顯示面板"""
        # TODO: Phase 5 - 實作右側面板
        right_frame = ttk.Frame(parent)
        parent.add(right_frame, weight=3)
        
        # 標題
        ttk.Label(
            right_frame,
            text="觀察中的股票",
            font=('Arial', 12, 'bold')
        ).pack(pady=5)
        
        # 滾動區域
        canvas = tk.Canvas(right_frame)
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        self.stocks_container = ttk.Frame(canvas)
        
        self.stocks_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.stocks_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")
        
        # 空狀態提示
        self.empty_label = ttk.Label(
            self.stocks_container,
            text="📊 尚未加入任何股票\n\n請從左側清單選擇股票加入觀察",
            font=('Arial', 12),
            foreground='gray'
        )
        self.empty_label.pack(pady=50)
    
    def load_tw_stocks(self):
        """載入台灣股票清單"""
        # TODO: Phase 4.1 - 整合 twstock
        try:
            # 取得所有上市公司代碼
            self.all_stocks = []
            
            # twstock.codes 包含所有股票代碼資訊
            for code, info in twstock.codes.items():
                if info.type == '股票':  # 只顯示股票類型
                    display_text = f"{code} - {info.name}"
                    self.all_stocks.append((code, info.name, display_text))
            
            # 依代碼排序
            self.all_stocks.sort(key=lambda x: x[0])
            
            # 顯示在列表中
            for _, _, display_text in self.all_stocks:
                self.stock_listbox.insert(tk.END, display_text)
            
            print(f"✓ 載入 {len(self.all_stocks)} 支台灣股票")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"載入股票清單失敗: {e}")
    
    def on_search(self, *args):
        """搜尋框文字變更時觸發"""
        # TODO: Phase 4.3 - 實作搜尋功能
        search_text = self.search_var.get().lower()
        
        self.stock_listbox.delete(0, tk.END)
        
        for code, name, display_text in self.all_stocks:
            if search_text in code.lower() or search_text in name.lower():
                self.stock_listbox.insert(tk.END, display_text)
    
    def on_stock_double_click(self, event):
        """雙擊股票項目時加入觀察清單"""
        self.add_to_watchlist()
    
    def add_to_watchlist(self):
        """加入股票到觀察清單"""
        # TODO: Phase 4.4 - 實作加入功能
        selection = self.stock_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "請先選擇一支股票")
            return
        
        selected_text = self.stock_listbox.get(selection[0])
        stock_code = selected_text.split(' - ')[0]
        
        if stock_code in self.watchlist:
            messagebox.showinfo("提示", f"股票 {stock_code} 已在觀察清單中")
            return
        
        self.watchlist.add(stock_code)
        messagebox.showinfo("成功", f"已加入股票 {stock_code} 到觀察清單")
        
        # 更新顯示
        self.update_watchlist_display()
    
    def remove_from_watchlist(self, stock_code: str):
        """從觀察清單移除股票"""
        if stock_code in self.watchlist:
            self.watchlist.remove(stock_code)
            if stock_code in self.stock_data_cache:
                del self.stock_data_cache[stock_code]
            self.update_watchlist_display()
    
    def update_watchlist_display(self):
        """更新右側觀察清單顯示"""
        # TODO: Phase 5 - 實作資料顯示
        # 清空現有顯示
        for widget in self.stocks_container.winfo_children():
            widget.destroy()
        
        if not self.watchlist:
            # 顯示空狀態
            self.empty_label = ttk.Label(
                self.stocks_container,
                text="📊 尚未加入任何股票\n\n請從左側清單選擇股票加入觀察",
                font=('Arial', 12),
                foreground='gray'
            )
            self.empty_label.pack(pady=50)
        else:
            # 顯示每支股票的資訊卡片
            for stock_code in sorted(self.watchlist):
                self.create_stock_card(stock_code)
    
    def create_stock_card(self, stock_code: str):
        """建立股票資訊卡片"""
        # 取得快取資料
        stock_data = self.stock_data_cache.get(stock_code)
        
        # 判斷漲跌，決定顏色
        change_str = stock_data.get('漲跌', '0') if stock_data else '0'
        try:
            change_value = float(change_str)
            if change_value > 0:
                color = '#28a745'  # 綠色 (上漲)
                arrow = '📈'
            elif change_value < 0:
                color = '#dc3545'  # 紅色 (下跌)
                arrow = '📉'
            else:
                color = '#6c757d'  # 灰色 (持平)
                arrow = '➡️'
        except:
            color = '#6c757d'
            arrow = '➡️'
        
        # 主卡片框架
        card_frame = tk.Frame(self.stocks_container, bg='white', relief=tk.RAISED, bd=1)
        card_frame.pack(fill=tk.X, padx=10, pady=8)
        
        if stock_data:
            # === 頂部區域：股票名稱 + 移除按鈕 ===
            header_frame = tk.Frame(card_frame, bg='white')
            header_frame.pack(fill=tk.X, padx=12, pady=(10, 5))
            
            # 左側：股票名稱和代碼
            left_header = tk.Frame(header_frame, bg='white')
            left_header.pack(side=tk.LEFT, expand=True)
            
            name_label = tk.Label(
                left_header,
                text=f"{stock_data.get('股票名稱', 'N/A')} ({stock_data.get('股票號碼', stock_code)})",
                font=('Arial', 13, 'bold'),
                bg='white',
                fg='#333333'
            )
            name_label.pack(anchor=tk.W)
            
            # 右側：移除按鈕
            remove_btn = tk.Button(
                header_frame,
                text="✕ 移除",
                command=lambda: self.remove_from_watchlist(stock_code),
                bg='#f0f0f0',
                fg='#666666',
                font=('Arial', 10),
                relief=tk.FLAT,
                padx=8,
                pady=2,
                cursor='hand2'
            )
            remove_btn.pack(side=tk.RIGHT)
            
            # === 中間區域：關鍵資訊（突出顯示）===
            key_info_frame = tk.Frame(card_frame, bg='white')
            key_info_frame.pack(fill=tk.X, padx=12, pady=10)
            
            # 股價
            price_frame = tk.Frame(key_info_frame, bg='white')
            price_frame.pack(side=tk.LEFT, padx=(0, 20))
            
            price_label = tk.Label(price_frame, text="即時價格", font=('Arial', 9), bg='white', fg='#999999')
            price_label.pack()
            price_value = tk.Label(
                price_frame,
                text=f"{stock_data.get('即時價格', 'N/A')}",
                font=('Arial', 20, 'bold'),
                bg='white',
                fg='#1a1a1a'
            )
            price_value.pack()
            
            # 漲跌幅（重點突出）
            change_frame = tk.Frame(key_info_frame, bg=color, relief=tk.RAISED, bd=1)
            change_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
            
            change_label = tk.Label(change_frame, text="漲跌", font=('Arial', 9), bg=color, fg='white')
            change_label.pack(pady=(5, 2))
            
            change_info = tk.Label(
                change_frame,
                text=f"{arrow} {change_str}",
                font=('Arial', 16, 'bold'),
                bg=color,
                fg='white'
            )
            change_info.pack()
            
            change_rate = tk.Label(
                change_frame,
                text=f"{stock_data.get('漲跌百分比', 'N/A')}",
                font=('Arial', 12, 'bold'),
                bg=color,
                fg='white'
            )
            change_rate.pack(pady=(0, 5))
            
            # === 下方區域：詳細資訊 ===
            detail_frame = tk.Frame(card_frame, bg='#f9f9f9')
            detail_frame.pack(fill=tk.X, padx=0, pady=0)
            
            # 左列資訊
            left_detail = tk.Frame(detail_frame, bg='#f9f9f9')
            left_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=8)
            
            detail_items = [
                ("開盤", stock_data.get('開盤價', 'N/A')),
                ("最高", stock_data.get('最高價', 'N/A')),
                ("最低", stock_data.get('最低價', 'N/A')),
            ]
            
            for label, value in detail_items:
                row = tk.Frame(left_detail, bg='#f9f9f9')
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=label, font=('Arial', 9), bg='#f9f9f9', fg='#999999', width=6).pack(side=tk.LEFT)
                tk.Label(row, text=value, font=('Arial', 10), bg='#f9f9f9', fg='#333333').pack(side=tk.LEFT)
            
            # 右列資訊
            right_detail = tk.Frame(detail_frame, bg='#f9f9f9')
            right_detail.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=12, pady=8)
            
            detail_items_right = [
                ("成交量", stock_data.get('成交量(張)', 'N/A')),
                ("昨收", stock_data.get('前一日收盤價', 'N/A')),
                ("更新", stock_data.get('update_time', 'N/A').split(' ')[1] if stock_data.get('update_time') else 'N/A'),
            ]
            
            for label, value in detail_items_right:
                row = tk.Frame(right_detail, bg='#f9f9f9')
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=label, font=('Arial', 9), bg='#f9f9f9', fg='#999999', width=6).pack(side=tk.LEFT)
                tk.Label(row, text=value, font=('Arial', 10), bg='#f9f9f9', fg='#333333').pack(side=tk.LEFT)
        
        else:
            # 等待資料狀態
            loading_frame = tk.Frame(card_frame, bg='white')
            loading_frame.pack(fill=tk.X, padx=12, pady=20)
            
            tk.Label(
                loading_frame,
                text=f"股票 {stock_code}",
                font=('Arial', 12, 'bold'),
                bg='white',
                fg='#333333'
            ).pack(anchor=tk.W, pady=(0, 8))
            
            tk.Label(
                loading_frame,
                text="⏳ 等待更新資料...",
                font=('Arial', 11),
                bg='white',
                fg='#999999'
            ).pack(anchor=tk.W)
    
    def manual_update(self):
        """手動更新股票資料"""
        # TODO: Phase 6.1 - 實作手動更新
        if not self.watchlist:
            messagebox.showinfo("提示", "觀察清單為空，請先加入股票")
            return
        
        if self.is_updating:
            messagebox.showinfo("提示", "正在更新中，請稍候...")
            return
        
        self.start_update()
    
    def start_update(self):
        """開始更新股票資料"""
        self.is_updating = True
        self.update_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"🔄 更新中... (0/{len(self.watchlist)})")
        
        # 在背景執行緒中執行爬蟲
        stock_codes = list(self.watchlist)
        thread = threading.Thread(
            target=run_crawler_in_thread,
            args=(stock_codes, self.result_queue),
            daemon=True
        )
        thread.start()
    
    def check_queue(self):
        """檢查爬蟲結果佇列"""
        try:
            while True:
                msg_type, data = self.result_queue.get_nowait()
                
                if msg_type == 'success':
                    self.on_update_complete(data)
                elif msg_type == 'error':
                    self.on_update_error(data)
                    
        except queue.Empty:
            pass
        
        # 每 100ms 檢查一次
        self.root.after(100, self.check_queue)
    
    def on_update_complete(self, results: List[Dict]):
        """更新完成回調"""
        # 更新快取
        for stock_data in results:
            stock_code = stock_data.get('stock_code')
            if stock_code:
                self.stock_data_cache[stock_code] = stock_data
        
        # 更新顯示
        self.update_watchlist_display()
        
        # 更新狀態
        self.is_updating = False
        self.update_btn.config(state=tk.NORMAL)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.status_label.config(text=f"✓ 更新完成")
        self.last_update_label.config(text=f"最後更新: {current_time}")
        
        print(f"✓ 成功更新 {len(results)}/{len(self.watchlist)} 支股票")
    
    def on_update_error(self, error_msg: str):
        """更新錯誤回調"""
        self.is_updating = False
        self.update_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"✗ 更新失敗")
        messagebox.showerror("錯誤", f"更新股票資料時發生錯誤:\n{error_msg}")
    
    def toggle_auto_update(self):
        """切換自動更新狀態"""
        # TODO: Phase 6.2 - 實作自動更新
        self.auto_update_enabled = self.auto_update_var.get()
        
        if self.auto_update_enabled:
            print("✓ 啟用自動更新（每 60 秒）")
            self.schedule_auto_update()
        else:
            print("✗ 停用自動更新")
            if self.update_timer_id:
                self.root.after_cancel(self.update_timer_id)
                self.update_timer_id = None
    
    def schedule_auto_update(self):
        """排程自動更新"""
        if self.auto_update_enabled and self.watchlist and not self.is_updating:
            self.start_update()
        
        # 每 60 秒執行一次
        if self.auto_update_enabled:
            self.update_timer_id = self.root.after(60000, self.schedule_auto_update)
    
    def on_closing(self):
        """視窗關閉事件處理"""
        if self.update_timer_id:
            self.root.after_cancel(self.update_timer_id)
        
        self.root.destroy()


# ==================== 主程式入口 ====================

def main():
    """應用程式主入口"""
    root = tk.Tk()
    app = StockMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()