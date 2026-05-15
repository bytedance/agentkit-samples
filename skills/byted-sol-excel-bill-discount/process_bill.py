#!/usr/bin/env python3
import pandas as pd
import sys
import os

# 完整的透视表字段顺序列表
ALL_FIELDS = [
    "账务账期",
    "Payer账号ID",
    "Payer ID",
    "Owner账号ID",
    "账号 ID",
    "产品",
    "商品",
    "计费模式",
    "账单类型",
    "配置名称",
    "计费单元",
    "单价",
    "单价单位",
    "优惠类型",
    "优惠内容",
    "用量",
    "原价",
    "折后价",
    "代金券抵扣",
    "应付金额",
]
# 需要居中对齐的字段
CENTER_COLUMNS = [
    "账务账期",
    "计费模式",
    "账单类型",
    "单价",
    "单价单位",
    "优惠类型",
    "优惠内容",
]
# 需要金额格式的字段
AMOUNT_FIELDS = ["原价", "折后价", "代金券抵扣", "应付金额"]
# 需要聚合求和的字段
AGG_FIELDS = ["用量", "原价", "折后价", "代金券抵扣", "应付金额"]


def calculate_column_width(series):
    """计算列的自适应宽度，中文计2单位，英文/数字计1单位，乘以1.1"""
    max_len = 0
    for cell in series.astype(str):
        length = sum(2 if "\u4e00" <= char <= "\u9fff" else 1 for char in cell)
        if length > max_len:
            max_len = length
    return max_len * 1.1


def parse_period(period_str):
    """统一将账务账期转换为YYYY-MM格式"""
    period_str = str(period_str).strip()
    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    try:
        if "-" in period_str:
            parts = period_str.split("-")
            if len(parts) >= 2:
                part1 = parts[0].strip()
                part2 = parts[1].strip()
                # 判断哪部分是月份
                if part1[:3].capitalize() in month_map:
                    # 格式：May-26 / May-2026
                    month = month_map[part1[:3].capitalize()]
                    year = part2
                    if len(year) == 2:
                        year = "20" + year
                    return f"{year}-{month}"
                elif part2[:3].capitalize() in month_map:
                    # 格式：26-May / 2026-May
                    month = month_map[part2[:3].capitalize()]
                    year = part1
                    if len(year) == 2:
                        year = "20" + year
                    return f"{year}-{month}"
                elif part1.isdigit() and part2.isdigit():
                    # 格式：2026-05 或 26-05
                    if len(part1) == 4:
                        return f"{part1}-{part2}"
                    elif len(part1) == 2:
                        return f"20{part1}-{part2}"
        # 处理纯数字格式：202605 / 2605
        if period_str.isdigit():
            if len(period_str) == 6:
                return f"{period_str[:4]}-{period_str[4:]}"
            elif len(period_str) == 4:
                return f"20{period_str[:2]}-{period_str[2:]}"
    except Exception:
        pass
    # 转换失败返回原格式
    return period_str


def main():
    if len(sys.argv) != 2:
        print("用法: python process_bill.py <输入账单Excel路径>")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"错误: 文件 {input_path} 不存在")
        sys.exit(1)

    try:
        # 读取文件，支持csv和excel格式
        file_ext = os.path.splitext(input_path)[1].lower()
        original_sheets = {}
        if file_ext == ".csv":
            # csv文件直接读取
            df = pd.read_csv(input_path)
            original_sheets["Sheet1"] = df
        else:
            # excel文件读取所有工作表
            excel_file = pd.ExcelFile(input_path)
            sheet_names = excel_file.sheet_names
            original_sheets = {name: excel_file.parse(name) for name in sheet_names}

        # 查找包含账务账期的源数据表
        source_df = None
        for name, df in original_sheets.items():
            if "账务账期" in df.columns:
                source_df = df
                break
        if source_df is None:
            print("错误: 未找到包含'账务账期'字段的工作表")
            sys.exit(1)

        # 统一转换账务账期和业务账期格式为YYYY-MM字符串
        source_df["账务账期"] = source_df["账务账期"].apply(
            lambda x: str(parse_period(x))
        )
        if "业务账期" in source_df.columns:
            source_df["业务账期"] = source_df["业务账期"].apply(
                lambda x: str(parse_period(x))
            )
        # 统一转换账务日期格式为YYYY/MM/DD，仅保留年月日，去除时分秒
        if "账务日期" in source_df.columns:
            # 先尝试转换为datetime类型，提取日期部分格式化为指定格式
            source_df["账务日期"] = pd.to_datetime(
                source_df["账务日期"], errors="coerce"
            ).dt.strftime("%Y/%m/%d")
            # 处理转换失败的异常值，保留原始内容
            source_df["账务日期"] = source_df["账务日期"].fillna(
                source_df["账务日期"].astype(str)
            )

        # 筛选原表实际存在的字段，按指定顺序排列
        actual_fields = [f for f in ALL_FIELDS if f in source_df.columns]
        if len(actual_fields) < 1:
            print("错误: 源数据未包含任何指定的有效字段")
            sys.exit(1)

        # 拆分分组字段和聚合字段
        group_fields = [f for f in actual_fields if f not in AGG_FIELDS]
        agg_fields = [f for f in actual_fields if f in AGG_FIELDS]

        # 计算原表对应字段的总额用于验证
        original_totals = {}
        for f in AMOUNT_FIELDS:
            if f in source_df.columns:
                original_totals[f] = source_df[f].sum()

        # 生成透视表：按分组字段聚合，dropna=False不忽略空值
        if group_fields and agg_fields:
            pivot_df = source_df.groupby(group_fields, dropna=False, as_index=False)[
                agg_fields
            ].sum()
        elif group_fields:
            pivot_df = source_df.groupby(
                group_fields, dropna=False, as_index=False
            ).first()
            # 仅保留需要的字段
            pivot_df = pivot_df[actual_fields]
        else:
            pivot_df = pd.DataFrame(columns=actual_fields)

        # 计算合计行：仅第一个分组列（账务账期）显示“合计”，其余分组列留白；用量不聚合留空
        total_row = {}
        for i, f in enumerate(group_fields):
            if i == 0:
                total_row[f] = "合计"
            else:
                total_row[f] = ""
        for f in agg_fields:
            if f == "用量":
                total_row[f] = ""
            else:
                total_row[f] = pivot_df[f].sum()
        if len(pivot_df) > 0:
            pivot_df = pd.concat(
                [pivot_df, pd.DataFrame([total_row])], ignore_index=True
            )
        else:
            pivot_df = pd.DataFrame([total_row])

        # 总额验证：仅验证原表存在的金额字段
        valid = True
        for f, original_total in original_totals.items():
            pivot_total = pivot_df[f].iloc[-1] if len(pivot_df) > 0 else 0
            if abs(pivot_total - original_total) > 0.01:
                valid = False
                break
        if not valid:
            print("错误: 总额不一致，无法生成")
            sys.exit(1)

        # 解析输出文件名
        first_period = str(source_df["账务账期"].iloc[0])
        parsed_period = parse_period(first_period)
        if "-" in parsed_period:
            year_part = parsed_period.split("-")[0][-2:]
            month_part = parsed_period.split("-")[1]
        else:
            # 解析失败时默认处理
            year_part = "00"
            month_part = "01"
        output_filename = f"{year_part}年{int(month_part)}月产品折扣账单.xlsx"
        output_path = os.path.join(os.path.dirname(input_path), output_filename)

        # 生成Excel文件，使用xlsxwriter确保无修复提示
        with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
            workbook = writer.book

            # 1. 新建账单折扣总览透视表，放在最左侧位置
            pivot_sheet = workbook.add_worksheet("账单折扣总览")
            writer.sheets["账单折扣总览"] = pivot_sheet

            # 定义格式
            # 通用格式：微软雅黑10号，边框
            general_format = workbook.add_format(
                {"font_name": "微软雅黑", "font_size": 10, "border": 1}
            )
            # 表头格式：蓝色填充，加粗居中
            header_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "bg_color": "#BDD7EE",
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            # 合计行居中格式：灰色填充，加粗居中
            total_center_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "bg_color": "#D9D9D9",
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            # 合计行金额格式：灰色填充，加粗居右，千分位2位小数
            total_amount_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "bg_color": "#D9D9D9",
                    "bold": True,
                    "num_format": "#,##0.00",
                    "align": "right",
                }
            )
            # 金额格式：2位小数，千位分隔符，居右
            amount_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "num_format": "#,##0.00",
                    "align": "right",
                }
            )
            # 居中格式
            center_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "align": "center",
                }
            )
            # 账务账期格式：YYYY-MM
            period_format = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "border": 1,
                    "num_format": "yyyy-mm",
                    "align": "center",
                }
            )
            # 用量格式：无特殊格式
            usage_format = workbook.add_format(
                {"font_name": "微软雅黑", "font_size": 10, "border": 1}
            )

            # 写入表头
            for col_idx, col_name in enumerate(actual_fields):
                pivot_sheet.write(0, col_idx, col_name, header_format)

            # 写入数据
            for row_idx in range(len(pivot_df)):
                row_data = pivot_df.iloc[row_idx]
                is_total = row_idx == len(pivot_df) - 1
                for col_idx, col_name in enumerate(actual_fields):
                    value = row_data[col_name]
                    # 格式适配
                    if is_total:
                        # 合计行全部灰色填充加粗：金额列居右带千分位，其他列居中
                        if col_name in AMOUNT_FIELDS:
                            fmt = total_amount_format
                        else:
                            fmt = total_center_format
                    elif col_name in AMOUNT_FIELDS:
                        fmt = amount_format
                    elif col_name == "用量":
                        fmt = usage_format
                    elif col_name == "账务账期":
                        fmt = period_format
                    elif col_name in CENTER_COLUMNS:
                        fmt = center_format
                    else:
                        fmt = general_format

                    pivot_sheet.write(row_idx + 1, col_idx, value, fmt)

            # 设置列宽自适应
            for col_idx, col_name in enumerate(actual_fields):
                col_series = pivot_df[col_name].astype(str)
                # 表头也要算入长度
                header_len = (
                    sum(2 if "\u4e00" <= char <= "\u9fff" else 1 for char in col_name)
                    * 1.1
                )
                content_len = calculate_column_width(col_series)
                width = max(header_len, content_len, 8)  # 最小宽度8
                # 限制特定列的最大宽度，避免过宽
                if col_name == "账务账期":
                    width = min(width, 12)
                elif col_name in AMOUNT_FIELDS:
                    width = min(width, 15)  # 金额字段最大宽度15，避免过宽
                pivot_sheet.set_column(col_idx, col_idx, width)

            # 设置透视表缩放90%
            pivot_sheet.set_zoom(90)

            # 2. 写入原数据表，统一命名为“明细账单”
            original_font_format = workbook.add_format(
                {"font_name": "等线", "font_size": 11}
            )
            # 原表日期格式
            date_format_ym = workbook.add_format(
                {"num_format": "yyyy-mm", "font_name": "等线", "font_size": 11}
            )
            date_format_ymd = workbook.add_format(
                {"num_format": "yyyy/mm/dd", "font_name": "等线", "font_size": 11}
            )
            date_format_ymdhms = workbook.add_format(
                {
                    "num_format": "yyyy/mm/dd hh:mm:ss",
                    "font_name": "等线",
                    "font_size": 11,
                }
            )

            # 直接写入源数据到“明细账单”工作表，忽略其他原工作表
            source_df.to_excel(writer, sheet_name="明细账单", index=False)
            worksheet = writer.sheets["明细账单"]
            # 设置默认字体为等线11号
            worksheet.set_default_row(15, original_font_format)
            # 处理日期字段格式
            for col_idx, col_name in enumerate(source_df.columns):
                if col_name in ["账务账期", "业务账期"]:
                    worksheet.set_column(col_idx, col_idx, None, date_format_ym)
                elif col_name == "账务日期":
                    worksheet.set_column(col_idx, col_idx, None, date_format_ymd)
                elif col_name in [
                    "消费开始时间(UTC+8)",
                    "消费结束时间(UTC+8)",
                    "交易时间(UTC+8)",
                ]:
                    worksheet.set_column(col_idx, col_idx, None, date_format_ymdhms)
                else:
                    worksheet.set_column(col_idx, col_idx, None, original_font_format)
            # 设置缩放90%
            worksheet.set_zoom(90)

            # 调整工作表顺序，将账单折扣总览移到最左侧
            workbook.worksheets_objs.sort(
                key=lambda x: 0 if x.name == "账单折扣总览" else 1
            )

        print(f"账单处理完成，输出文件: {output_path}")
        # 保存输出路径以便后续发送
        with open("/tmp/last_output_bill.txt", "w") as f:
            f.write(output_path)
        sys.exit(0)

    except Exception as e:
        print(f"处理失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
