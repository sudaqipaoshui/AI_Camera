#!/bin/bash
# 启用Android模拟器的指针位置和触摸显示

echo "正在启用指针位置和触摸显示..."

# 启用指针位置（显示鼠标轨迹和坐标）
adb shell settings put system pointer_location 1

# 启用触摸显示（显示触摸点）
adb shell settings put system show_touches 1

# 验证设置
echo ""
echo "当前设置状态:"
echo "指针位置: $(adb shell settings get system pointer_location)"
echo "触摸显示: $(adb shell settings get system show_touches)"

echo ""
echo "✅ 已启用指针位置和触摸显示"
echo "现在可以在模拟器屏幕上看到鼠标轨迹和触摸位置了"










