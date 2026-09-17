def extract_first_last(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f_in, \
            open(output_path, 'w', encoding='utf-8') as f_out:

        current_segment = []
        in_segment = False

        for line in f_in:
            stripped_line = line.strip()
            # 检测新的数据段开始
            if stripped_line.startswith('第 ') and '段数据' in stripped_line:
                # 先处理上一个未完成的段
                if in_segment and current_segment:
                    # 提取第一条和最后一条
                    first = current_segment[0]
                    last = current_segment[-1]
                    f_out.write(f"===== 上一段数据 首尾提取 =====\n")
                    f_out.write(f"第一条：{first}\n")
                    f_out.write(f"最后一条：{last}\n\n")
                # 重置当前段
                current_segment = []
                in_segment = True
                f_out.write(f"===== 处理 {stripped_line} =====\n")
            # 收集数据行（以数字+. frameId开头的行）
            elif in_segment and stripped_line and stripped_line[0].isdigit() and '. frameId' in stripped_line:
                current_segment.append(stripped_line)

        # 处理文件末尾的最后一个段
        if in_segment and current_segment:
            first = current_segment[0]
            last = current_segment[-1]
            f_out.write(f"===== 最后一段数据 首尾提取 =====\n")
            f_out.write(f"第一条：{first}\n")
            f_out.write(f"最后一条：{last}\n")


# 配置输入输出路径
input_file = "/Volumes/ExtDisk/test_x5/QA/automation/AICameraTestLab/allure-report/long_jump/20260120_173343/final_result_拆分后分组数据.txt"  # 你的输入文件
output_file = "/Volumes/ExtDisk/test_x5/QA/automation/AICameraTestLab/allure-report/long_jump/20260120_173343/提取结果_首尾记录.txt"  # 输出文件

# 执行提取
extract_first_last(input_file, output_file)
print(f"✅ 提取完成！结果已保存到 {output_file}")