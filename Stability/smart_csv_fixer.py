#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能CSV修复工具
自动检测和修复CSV格式问题，支持多种修复策略
"""

import pandas as pd
import os
import sys
import csv
from datetime import datetime

class SmartCSVFixer:
    def __init__(self, csv_file_path):
        self.csv_file_path = csv_file_path
        self.backup_path = csv_file_path + '.backup'
        self.standard_columns = None
        self.fix_strategies = {
            'truncate': '截取前面的字段',
            'pad': '用空值填充缺失字段',
            'merge': '智能合并字段',
            'reorder': '重新排序字段'
        }
    
    def analyze_structure(self):
        """分析CSV文件结构"""
        print(f"分析CSV文件结构: {self.csv_file_path}")
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"总行数: {len(lines)}")
            
            # 分析每行的字段数量
            field_counts = {}
            for line_num, line in enumerate(lines, 1):
                if line.strip():
                    field_count = len(line.strip().split(','))
                    if field_count not in field_counts:
                        field_counts[field_count] = []
                    field_counts[field_count].append(line_num)
            
            print("\n字段数量分布:")
            for count, line_numbers in field_counts.items():
                print(f"  {count} 个字段: {len(line_numbers)} 行 (行号: {line_numbers[:5]}{'...' if len(line_numbers) > 5 else ''})")
            
            # 显示第一行作为参考
            if lines:
                print(f"\n第一行 (标题行): {lines[0].strip()}")
                print(f"标题行字段数: {len(lines[0].strip().split(','))}")
                self.standard_columns = lines[0].strip().split(',')
            
            return field_counts
            
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            return None
    
    def create_backup(self):
        """创建备份文件"""
        if not os.path.exists(self.backup_path):
            import shutil
            shutil.copy2(self.csv_file_path, self.backup_path)
            print(f"已创建备份文件: {self.backup_path}")
        else:
            print(f"备份文件已存在: {self.backup_path}")
    
    def fix_with_strategy(self, strategy='truncate'):
        """使用指定策略修复CSV文件"""
        print(f"\n使用策略 '{strategy}' ({self.fix_strategies[strategy]}) 修复CSV文件...")
        
        try:
            # 创建备份
            self.create_backup()
            
            # 读取原始CSV文件
            with open(self.csv_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            fixed_lines = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                fields = line.split(',')
                current_field_count = len(fields)
                
                if current_field_count == len(self.standard_columns):
                    # 字段数量正确
                    fixed_lines.append(line)
                elif current_field_count > len(self.standard_columns):
                    # 字段过多
                    if strategy == 'truncate':
                        print(f"第{line_num}行字段过多 ({current_field_count} > {len(self.standard_columns)})，截取前{len(self.standard_columns)}个字段")
                        fixed_line = ','.join(fields[:len(self.standard_columns)])
                        fixed_lines.append(fixed_line)
                    elif strategy == 'merge':
                        # 智能合并：将多余的字段合并到最后一个字段中
                        print(f"第{line_num}行字段过多，合并多余字段")
                        base_fields = fields[:len(self.standard_columns)-1]
                        merged_field = ','.join(fields[len(self.standard_columns)-1:])
                        fixed_line = ','.join(base_fields + [merged_field])
                        fixed_lines.append(fixed_line)
                else:
                    # 字段不足
                    if strategy == 'pad':
                        print(f"第{line_num}行字段不足 ({current_field_count} < {len(self.standard_columns)})，用空值填充")
                        missing_fields = [''] * (len(self.standard_columns) - current_field_count)
                        fixed_line = line + ',' + ','.join(missing_fields)
                        fixed_lines.append(fixed_line)
                    elif strategy == 'truncate':
                        # 截取策略：如果字段不足，保持原样（可能是标题行）
                        fixed_lines.append(line)
            
            # 写入修复后的文件
            print("正在写入修复后的文件...")
            with open(self.csv_file_path, 'w', encoding='utf-8') as f:
                for line in fixed_lines:
                    f.write(line + '\n')
            
            print(f"✅ CSV文件修复完成！")
            print(f"修复了 {len(fixed_lines)} 行数据")
            
            return True
            
        except Exception as e:
            print(f"❌ 修复失败: {e}")
            return False
    
    def validate_fix(self):
        """验证修复结果"""
        print("\n验证修复结果...")
        try:
            df = pd.read_csv(self.csv_file_path)
            print(f"✅ 验证成功！数据形状: {df.shape}")
            print(f"列数: {len(df.columns)}")
            print(f"行数: {len(df)}")
            print(f"列名: {list(df.columns)}")
            return True
        except Exception as e:
            print(f"❌ 验证失败: {e}")
            return False
    
    def auto_fix(self):
        """自动修复CSV文件"""
        print("开始自动修复CSV文件...")
        
        # 1. 分析结构
        field_counts = self.analyze_structure()
        if not field_counts:
            return False
        
        # 2. 如果只有一种字段数量，无需修复
        if len(field_counts) == 1:
            print("✅ CSV文件格式正常，无需修复")
            return True
        
        # 3. 选择修复策略
        max_count = max(field_counts.keys())
        min_count = min(field_counts.keys())
        
        if max_count > len(self.standard_columns):
            # 有字段过多的情况，使用截取策略
            strategy = 'truncate'
        elif min_count < len(self.standard_columns):
            # 有字段不足的情况，使用填充策略
            strategy = 'pad'
        else:
            # 默认使用截取策略
            strategy = 'truncate'
        
        print(f"选择修复策略: {strategy}")
        
        # 4. 执行修复
        success = self.fix_with_strategy(strategy)
        if not success:
            return False
        
        # 5. 验证修复结果
        return self.validate_fix()
    
    def restore_backup(self):
        """恢复备份文件"""
        if os.path.exists(self.backup_path):
            import shutil
            shutil.copy2(self.backup_path, self.csv_file_path)
            print(f"已从备份恢复文件: {self.csv_file_path}")
            return True
        else:
            print("❌ 备份文件不存在")
            return False

def main():
    print("智能CSV修复工具")
    print("=" * 50)
    
    # 默认CSV文件路径
    default_csv = "allure-report/24h-monitoring/2025-12-31/ssh_monitoring_data.csv"
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = default_csv
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV文件不存在: {csv_file}")
        sys.exit(1)
    
    # 创建修复器
    fixer = SmartCSVFixer(csv_file)
    
    # 执行自动修复
    success = fixer.auto_fix()
    
    if success:
        print("\n✅ 自动修复完成！")
    else:
        print("\n❌ 自动修复失败")
        print("可以尝试手动恢复备份文件:")
        print(f"  python {sys.argv[0]} --restore")
    
    # 处理恢复命令
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        fixer.restore_backup()

if __name__ == "__main__":
    main()
