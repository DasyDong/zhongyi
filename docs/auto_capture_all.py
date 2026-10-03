"""
全自动截图工具 - 自动点击左侧菜单项，依次截取所有功能界面。
使用方法：
1. 先启动中医软件并登录，保持窗口可见（不需要在前台）
2. 运行：python docs\auto_capture_all.py
"""
import os
import time
import win32gui
import win32ui
import win32api
import win32con
from ctypes import windll
from PIL import Image

SAVE_DIR = r"d:\code\zhongyi\docs\user_manual\images"
WINDOW_KEYWORD = "建华"

# 左侧菜单项（从上到下的顺序），每项对应输出文件名
MENU_ITEMS = [
    ("患者", "02_main_patient.png"),
    ("病症表现", "04_symptoms.png"),
    ("辨证分析", "05_analysis.png"),
    ("诊断结论", "06_diagnosis.png"),
    ("针灸", "07_acupuncture.png"),
    ("方剂", "08_formulas.png"),
    ("药品列表", "09_drug_list.png"),
    ("用法", "10_usage.png"),
    ("病历记录", "11_medical_record.png"),
    ("用户信息", "12_user_info.png"),
]

def find_window():
    result = []
    def callback(h, _):
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h)
            if WINDOW_KEYWORD in title:
                result.append((h, title))
        return True
    win32gui.EnumWindows(callback, None)
    return result

def capture_window(hwnd, save_path):
    """截取整个窗口"""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width < 100 or height < 100:
        return False
    
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    
    result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
    
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                           bmpstr, 'raw', 'BGRX', 0, 1)
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    
    if result:
        img.save(save_path)
        return True
    return False

def click_at(hwnd, x, y):
    """在窗口的客户区坐标 (x, y) 处模拟鼠标点击"""
    # 转换为屏幕坐标
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    screen_x = left + x
    screen_y = top + y
    
    # 移动鼠标
    win32api.SetCursorPos((screen_x, screen_y))
    time.sleep(0.1)
    
    # 按下左键
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
    time.sleep(0.05)
    
    # 释放左键
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
    time.sleep(0.1)

def main():
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    # 查找窗口
    windows = find_window()
    if not windows:
        print("❌ 未找到中医软件窗口，请先启动并登录")
        return
    
    hwnd, title = windows[0]
    print(f"✅ 找到窗口：{title}")
    
    # 获取窗口尺寸
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w = right - left
    h = bottom - top
    print(f"📐 窗口尺寸：{w} x {h}")
    
    # 将窗口调到前台
    try:
        win32gui.SetForegroundWindow(hwnd)
    except:
        pass
    time.sleep(0.5)
    
    # 估算左侧菜单栏按钮位置
    # 左侧 Sidebar 宽度约 60-70px
    # 按钮从上到下排列，每个约 50-55px 高
    # 顶部约有 80-100px 的间距（logo/标题区域）
    sidebar_x = 35  # 侧边栏中心 X 坐标
    button_start_y = 110  # 第一个按钮中心 Y 坐标
    button_height = 53  # 每个按钮高度
    
    print()
    print("=" * 60)
    print("📸 开始自动截图...")
    print("=" * 60)
    
    success_count = 0
    
    for i, (menu_name, filename) in enumerate(MENU_ITEMS):
        # 计算按钮位置
        btn_y = button_start_y + i * button_height
        
        print(f"\n[{i+1}/{len(MENU_ITEMS)}] 点击：{menu_name}  →  {filename}")
        
        # 点击菜单项
        click_at(hwnd, sidebar_x, btn_y)
        
        # 等待界面切换
        time.sleep(0.8)
        
        # 截图
        filepath = os.path.join(SAVE_DIR, filename)
        success = capture_window(hwnd, filepath)
        if success:
            print(f"   ✅ 已保存")
            success_count += 1
        else:
            print(f"   ❌ 失败")
    
    # 最后回到患者界面
    click_at(hwnd, sidebar_x, button_start_y + 0 * button_height)
    time.sleep(0.5)
    
    print()
    print("=" * 60)
    print(f"🏁 完成！成功截图 {success_count}/{len(MENU_ITEMS)} 张")
    print(f"📂 保存目录：{SAVE_DIR}")
    print()
    print("如果截图位置不准，请调整脚本中的 sidebar_x, button_start_y, button_height 参数")

if __name__ == "__main__":
    main()
