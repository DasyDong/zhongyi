"""
一键截图工具 - 用户手动切换界面，按空格键截图，自动用功能名保存。
使用方法：
1. 先启动中医软件并登录，保持窗口在前台
2. 运行本脚本：python docs\auto_capture.py
3. 切换到软件的某个功能界面
4. 按空格键截图（脚本会用预设的功能名保存）
5. 按 ESC 键退出
"""
import os
import win32gui
import win32ui
from ctypes import windll, wintypes
from PIL import Image
import threading

SAVE_DIR = r"d:\code\zhongyi\docs\user_manual\images"
WINDOW_KEYWORD = "建华"

# 截图清单：按顺序命名，用户每按一次空格就存下一张
SCREENSHOT_LIST = [
    "02_main_patient.png",       # 主界面-患者
    "03_patient_detail.png",    # 患者详情
    "04_symptoms.png",          # 病症表现
    "05_analysis.png",          # 辨证分析
    "06_diagnosis.png",         # 诊断结论
    "07_acupuncture.png",       # 针灸
    "08_formulas.png",          # 方剂
    "09_drug_list.png",         # 药品列表
    "10_usage.png",             # 用法
    "11_medical_record.png",    # 病历记录
    "12_user_info.png",         # 用户信息
    "13_prescription_report.png", # 处方报告预览
    "14_case_report.png",       # 病例报告预览
    "15_db_config.png",         # 数据库配置
]

current_index = 0
hwnd = None

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

def on_key_event(event):
    global current_index, hwnd
    if event.Key == "space":
        if current_index >= len(SCREENSHOT_LIST):
            print("\n🎉 全部截图完成！按 ESC 退出。")
            return
        filename = SCREENSHOT_LIST[current_index]
        filepath = os.path.join(SAVE_DIR, filename)
        
        # 重新查找窗口（防止最小化等情况）
        windows = find_window()
        if windows:
            hwnd = windows[0][0]
        
        if hwnd:
            # 把窗口调到前台
            try:
                win32gui.SetForegroundWindow(hwnd)
            except:
                pass
            import time
            time.sleep(0.3)  # 等待窗口激活
            
            success = capture_window(hwnd, filepath)
            if success:
                current_index += 1
                remaining = len(SCREENSHOT_LIST) - current_index
                print(f"✅ 已保存：{filename}  （还剩 {remaining} 张）")
            else:
                print(f"❌ 截图失败：{filename}")
        else:
            print("❌ 找不到程序窗口")
        return False  # 不抑制按键

def main():
    global hwnd
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    windows = find_window()
    if not windows:
        print("❌ 未找到中医软件窗口")
        print("   请先启动 建华卫生所中医处方系统 并登录")
        input("   启动后按回车键继续...")
        windows = find_window()
        if not windows:
            print("❌ 还是没找到，退出")
            return
    
    hwnd, title = windows[0]
    print(f"✅ 找到窗口：{title}")
    print()
    print("=" * 50)
    print("📸 截图清单（按空格依次截取）：")
    print("=" * 50)
    for i, name in enumerate(SCREENSHOT_LIST, 1):
        print(f"   {i:2d}. {name}")
    print("=" * 50)
    print()
    print("操作说明：")
    print("  空格键  →  截取当前界面，保存为下一张")
    print("  ESC 键  →  退出")
    print()
    print("请切换到第一个界面，按空格开始截图...")
    
    try:
        import pythoncom
        import pyHook
        hm = pyHook.HookManager()
        hm.KeyDown = on_key_event
        hm.HookKeyboard()
        pythoncom.PumpMessages()
    except ImportError:
        # 没有 pyHook，用 msvcrt 简单实现
        print("(使用简单模式：在控制台按回车截图，输入 q 退出)")
        while current_index < len(SCREENSHOT_LIST):
            cmd = input(f"\n按回车截取第 {current_index + 1} 张 ({SCREENSHOT_LIST[current_index]})，输入 q 退出: ")
            if cmd.strip().lower() == 'q':
                break
            # 重新查找窗口
            wins = find_window()
            if wins:
                hwnd = wins[0][0]
            if hwnd:
                filename = SCREENSHOT_LIST[current_index]
                filepath = os.path.join(SAVE_DIR, filename)
                success = capture_window(hwnd, filepath)
                if success:
                    current_index += 1
                    print(f"✅ 已保存：{filename}")
                else:
                    print(f"❌ 失败")
            else:
                print("❌ 找不到窗口")
    
    print(f"\n🏁 共完成 {current_index} 张截图")
    print(f"📂 保存目录：{SAVE_DIR}")

if __name__ == "__main__":
    main()
