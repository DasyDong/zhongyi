"""
截图工具：截取中医软件各界面截图
需要 pywin32 和 PIL
"""
import time
import win32gui
import win32ui
import win32con
from ctypes import windll
from PIL import Image

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
    """截取指定窗口并保存为图片"""
    # 获取窗口尺寸
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    
    # 获取窗口DC
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    
    # 创建位图
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    
    # 打印窗口到位图
    result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)  # 2 = PW_RENDERFULLCONTENT
    
    # 获取位图信息
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    # 转换为PIL Image
    img = Image.frombuffer(
        'RGB',
        (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
        bmpstr, 'raw', 'BGRX', 0, 1
    )
    
    # 清理资源
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    
    if result:
        img.save(save_path)
        print(f"截图已保存: {save_path} ({width}x{height})")
        return True
    else:
        print(f"截图失败: {save_path}")
        return False

def main():
    time.sleep(2)  # 等待窗口完全显示
    
    # 查找窗口
    windows = find_window("建华")
    if not windows:
        windows = find_window("中医")
    if not windows:
        windows = find_window("ZhongYi")
    
    if not windows:
        print("未找到程序窗口，已有的可见窗口：")
        all_wins = []
        def cb(h, _):
            if win32gui.IsWindowVisible(h):
                t = win32gui.GetWindowText(h)
                if t:
                    all_wins.append(t[:50])
            return True
        win32gui.EnumWindows(cb, None)
        for t in all_wins[:20]:
            print(f"  - {t}")
        return
    
    print(f"找到 {len(windows)} 个窗口:")
    for hwnd, title in windows:
        print(f"  - {title}")
    
    # 截取第一个窗口（登录界面）
    hwnd, title = windows[0]
    capture_window(hwnd, r"d:\code\zhongyi\docs\user_manual\images\01_login.png")

if __name__ == "__main__":
    main()
