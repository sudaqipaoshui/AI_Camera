from PIL import Image
import os
import glob

def stitch_images(folder_path, output_path="stitched_image.jpg", images_per_row=2):

    # 1. 校验文件夹是否存在
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"文件夹不存在：{folder_path}")

    # 2. 获取文件夹内所有图片文件（支持jpg/png/jpeg格式）
    image_extensions = ("*.jpg", "*.png", "*.jpeg")
    image_paths = []
    for ext in image_extensions:
        image_paths.extend(glob.glob(os.path.join(folder_path, ext)))

    # 去重并按文件名排序（保证拼接顺序可预测）
    image_paths = sorted(list(set(image_paths)))
    total_images = len(image_paths)

    # 3. 校验是否有图片
    if total_images == 0:
        raise ValueError("指定文件夹内未找到图片文件（支持jpg/png/jpeg格式）")
    if total_images > 100:
        raise ValueError(f"图片数量({total_images})超过100张，不符合需求限制")

    # 4. 定义单张图片的标准尺寸 ,2369,,1317
    single_width = 2369
    single_height = 1317

    # 5. 读取并校验所有图片的尺寸
    images = []
    for idx, img_path in enumerate(image_paths):
        try:
            with Image.open(img_path) as img:
                # 校验尺寸是否符合要求
                if img.size != (single_width, single_height):
                    print(f"警告：图片{img_path}尺寸为{img.size}，不符合2369×1317标准，已跳过")
                    continue
                # 转换为RGB模式（避免PNG透明通道问题）
                img = img.convert("RGB")
                images.append(img)
        except Exception as e:
            print(f"读取图片{img_path}失败：{str(e)}，已跳过")

    # 重新统计有效图片数量
    valid_count = len(images)
    if valid_count == 0:
        raise ValueError("没有符合尺寸要求的有效图片")

    # 6. 计算拼接布局（行数和列数）
    rows = (valid_count + images_per_row - 1) // images_per_row  # 向上取整
    cols = min(valid_count, images_per_row)  # 最后一行可能不足

    # 7. 计算大画布的尺寸
    canvas_width = cols * single_width
    canvas_height = rows * single_height

    # 8. 创建空白画布（白色背景）
    stitched_image = Image.new("RGB", (canvas_width, canvas_height), "white")

    # 9. 逐个粘贴图片到画布
    for idx, img in enumerate(images):
        # 计算当前图片的坐标
        row_idx = idx // images_per_row
        col_idx = idx % images_per_row
        x = col_idx * single_width
        y = row_idx * single_height
        stitched_image.paste(img, (x, y))

    # 10. 保存拼接后的图片
    stitched_image.save(output_path, quality=95)
    print(f"拼接完成！共拼接{valid_count}张图片，结果已保存至：{output_path}")
    print(f"拼接后图片尺寸：{stitched_image.size}")


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    YOUR_FOLDER_PATH = "/Volumes/ExtDisk/test_x5/QA/automation/AICameraTestLab/allure-report/long_jump/20260121_140556/track_img_output"

    try:
        stitch_images(
            folder_path=YOUR_FOLDER_PATH,
            output_path="/Volumes/ExtDisk/test_x5/QA/automation/AICameraTestLab/allure-report/long_jump/20260121_140556/跳绳.jpg",  # 输出文件名可自定义
            images_per_row=2
        )
    except Exception as e:
        print(f"程序执行出错：{str(e)}")