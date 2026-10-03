"""
自动化截图工具：截取中医软件各功能界面截图
"""
import time
import win32gui
import win32ui
import win32con
import win32api
import ctypes
from ctypes import windll
from PIL import Image

# 截图保存目录
SAVE_DIR = r"d:\code\zhongyi\docs\user_manual\images"

# 虚拟键码
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

def find_window(title_keyword):
    """根据标题关键词查找窗口句柄"""
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_keyword in title:
                result.append((hwnd, title))
        return True
    win32gui.EnumWindows(callback, None)
    return result

def capture_window(hwnd, save_path):
    """截取指定窗口"""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    
    result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
    
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    img = Image.frombuffer(
        'RGB',
        (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
        bmpstr, 'raw', 'BGRX', 0, 1
    )
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    
    if result:
        img.save(save_path)
        print(f"  ✅ 截图保存: {save_path.split(chr(92))[-1]} ({width}x{height})")
        return True
    else:
        print(f"  ❌ 截图失败: {save_path}")
        return False

def bring_to_front(hwnd):
    """将窗口带到前台"""
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
    except:
        pass

def press_key(vk_code, delay=0.3):
    """模拟按键"""
    win32api.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(delay)

def send_text(text, delay=0.1):
    """输入文本"""
    for char in text:
        # 使用 SendInput 或 WM_CHAR 消息发送字符
        vk = win32api.VkKeyScan(char)
        if vk == -1:
            continue
        vk_code = vk & 0xFF
        shift = vk & 0x100
        
        if shift:
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        
        win32api.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.02)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        
        if shift:
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
        
        time.sleep(delay)

def click_at(hwnd, x, y, delay=0.5):
    """在窗口内指定位置点击"""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    screen_x = left + x
    screen_y = top + y
    
    # 移动鼠标并点击
    win32api.SetCursorPos((screen_x, screen_y))
    time.sleep(0.2)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
    time.sleep(delay)

def main():
    print("=" * 50)
    print("中医系统界面截图工具")
    print("=" * 50)
    
    # 等待窗口出现
    print("\n等待程序窗口...")
    for i in range(10):
        windows = find_window("建华")
        if windows:
            break
        time.sleep(1)
    
    if not windows:
        windows = find_window("中医")
    if not windows:
        windows = find_window("ZhongYi")
    
    if not windows:
        print("❌ 未找到程序窗口")
        return
    
    hwnd, title = windows[0]
    print(f"✅ 找到窗口: {title}")
    bring_to_front(hwnd)
    time.sleep(1)
    
    # --- 第1张：登录界面 ---
    print("\n[1/8] 登录界面...")
    capture_window(hwnd, f"{SAVE_DIR}\\01_login.png")
    
    # 模拟登录（输入用户名密码）
    print("  正在输入登录信息...")
    # Tab 到密码框（用户名框默认聚焦，先按Tab到密码）
    # 先输入用户名
    send_text("admin", 0.05)
    press_key(VK_TAB, 0.2)
    send_text("admin123", 0.05)
    press_key(VK_RETURN, 2.0)  # 回车登录，等待主界面加载
    
    # 重新获取窗口（标题可能变了）
    windows = find_window("建华")
    if windows:
        hwnd = windows[0][0]
        bring_to_front(hwnd)
    
    # --- 第2张：主界面（患者） ---
    print("\n[2/8] 主界面-患者管理...")
    time.sleep(1)
    capture_window(hwnd, f"{SAVE_DIR}\\02_main_patient.png")
    
    # 点击左侧菜单 - 病症表现（大致位置，左侧第3个按钮）
    print("\n[3/8] 病症表现界面...")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    click_at(hwnd, 80, 180, 1.0)  # 左侧菜单区域
    capture_window(hwnd, f"{SAVE_DIR}\\03_symptoms.png")
    
    # 辨证分析
    print("\n[4/8] 辨证分析界面...")
    click_at(hwnd, 80, 240, 1.0)
    capture_window(hwnd, f"{SAVE_DIR}\\04_analysis.png")
    
    # 诊断结论
    print("\n[5/8] 诊断结论界面...")
    click_at(hwnd, 80, 300, 1.0)
    capture_window(hwnd, f"{SAVE_DIR}\\05_diagnosis.png")
    
    # 针灸
    print("\n[6/8] 针灸设置界面...")
    click_at(hwnd, 80, 360, 1.0)
    capture_window(hwnd, f"{SAVE_DIR}\\06_acupuncture.png")
    
    # 方剂
    print("\n[7/8] 方剂管理界面...")
    click_at(hwnd, 80, 420, 1.0)
    capture_window(hwnd, f"{SAVE_DIR}\\07_formulas.png")
    
    # 药品列表
    print("\n[8/8] 药品列表界面...")
    click_at(hwnd, 80, 480, 1.0)
    capture_window(hwnd, f"{SAVE_DIR}\\08_drug_list.png")
    
    print("\n" + "=" * 50)
    print("✅ 截图完成！共 8 张截图")
    print(f"保存位置: {SAVE_DIR}")
    print("=" * 50)

if __name__ == "__main__":
    main()
