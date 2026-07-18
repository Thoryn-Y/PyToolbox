#!/usr/bin/env python3
"""
将 Word(.docx) 或 PDF 论文转换为 Markdown。
- 保留标题层级、正文段落、表格。
- 自动提取图片并保存到同目录，图片命名尽可能使用原文档中的图注（小标题）。
"""

import os
import sys
import re
import argparse
from pathlib import Path

# Word 处理
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx.oxml.ns as ns

# PDF 处理
import fitz  # PyMuPDF

# 注册 VML 命名空间（处理从网页粘贴到 Word 的图片）
ns.nsmap['v'] = 'urn:schemas-microsoft-com:vml'

# ---------- Word 转换部分 ----------
def extract_images_from_docx(doc, docx_path, output_dir):
    """
    从 docx 文档中提取所有图片关系，返回映射：{rId: 保存后的相对文件名}
    """
    image_map = {}
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            rId = rel.rId
            img = rel.target_part
            # 获取图片扩展名
            ext = Path(img.partname).suffix
            if not ext:
                ext = ".png"  # 默认
            # 用 rId 作为暂定文件名，稍后会根据图注重命名
            img_bytes = img.blob
            # 先用 rId 临时保存，后面遇到图片时会根据图注重命名
            # 这里先统一保存到临时名，真正插入时再重命名
            temp_name = f"_img_{rId}{ext}"
            temp_path = os.path.join(output_dir, temp_name)
            with open(temp_path, "wb") as f:
                f.write(img_bytes)
            image_map[rId] = temp_name
    return image_map


def get_image_title(paragraph, doc):
    """
    尝试获取图片的题注（小标题）：
    1. 检查图片所在段落的后一个段落，如果样式为 'Caption' 或包含 '图'/'Figure'，则返回其文本。
    2. 如果图片在段落内，该段落可能同时包含图片和题注文本（比如题注在图片后面），则尝试从段落文本中提取。
    返回标题字符串，若没有则返回 None。
    """
    # 如果图片在 run 中，该段落可能只是图片，题注通常在其后一个段落
    next_paragraph = paragraph  # 稍后向后查找
    parent = paragraph._element.getparent()
    if parent is None:
        return None
    # 找到当前段落在 body 中的索引
    children = list(parent)
    try:
        idx = children.index(paragraph._element)
    except ValueError:
        return None
    # 检查后一个段落
    if idx + 1 < len(children):
        next_elem = children[idx + 1]
        # 判断下一个元素是否为段落
        if next_elem.tag == ns.qn('w:p'):
            # 从 docx.text.paragraph 构造对象
            from docx.text.paragraph import Paragraph
            next_para = Paragraph(next_elem, paragraph._parent)
            if next_para.text.strip():
                text = next_para.text.strip()
                # 判断是否为题注（可按样式名称，通常为 Caption，但中文可能没有样式）
                if next_para.style and next_para.style.name == 'Caption':
                    return text
                # 也接受包含 图/Figure 的段落
                if re.match(r'^(图|Fig\.?|Figure)\s*\d', text, re.IGNORECASE):
                    return text
    return None


def docx_to_markdown(docx_path, output_dir):
    """将 Word 文档转为 Markdown 文件，返回输出的 md 文件路径"""
    doc = Document(docx_path)
    md_lines = []
    # 先提取所有图片到临时文件，并建立 rId -> 文件名的映射
    image_map = extract_images_from_docx(doc, docx_path, output_dir)

    # 用于给没有标题的图片编号
    img_counter = 0
    # 记录需要跳过的题注段落元素（已作为图片 alt text 输出）
    skip_elements = set()
    # 记录已使用的图片 rId，用于清理未引用的临时图片
    used_rIds = set()

    # 遍历文档中的段落和表格（按顺序）
    body = doc.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in body:
        if child.tag == ns.qn('w:p'):
            # 跳过已作为图片题注输出的段落
            if id(child) in skip_elements:
                continue
            para = Paragraph(child, doc)
            # 检查段落中是否有图片（inlineShapes）
            has_image = False
            image_title = None

            # 处理单张图片的通用逻辑：重命名、输出 Markdown、跳过题注
            def process_image(rId, alt_text=None):
                nonlocal img_counter
                if rId not in image_map:
                    return
                used_rIds.add(rId)
                # 优先使用 alt text，否则从后续段落获取题注
                title = alt_text
                if not title:
                    title = get_image_title(para, doc)
                if not title:
                    img_counter += 1
                    title = f"图 {img_counter}"
                # 重命名临时文件为题注名
                temp_name = image_map[rId]
                temp_path = os.path.join(output_dir, temp_name)
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
                ext = Path(temp_name).suffix
                new_name = f"{safe_title}{ext}"
                new_path = os.path.join(output_dir, new_name)
                # 如果同名文件已存在，循环递增编号直到不冲突
                if os.path.exists(new_path) and temp_path != new_path:
                    dup_counter = 1
                    base, ext = os.path.splitext(new_name)
                    while os.path.exists(new_path):
                        new_name = f"{base}_{dup_counter}{ext}"
                        new_path = os.path.join(output_dir, new_name)
                        dup_counter += 1
                os.rename(temp_path, new_path)
                md_lines.append(f"![{title}]({new_name})")
                # 如果题注是下一个段落，将其加入跳过集合，防止重复输出
                if title:
                    parent_elem = para._element.getparent()
                    if parent_elem is not None:
                        siblings = list(parent_elem)
                        try:
                            cur_idx = siblings.index(para._element)
                            if cur_idx + 1 < len(siblings):
                                next_elem = siblings[cur_idx + 1]
                                if next_elem.tag == ns.qn('w:p'):
                                    next_p = Paragraph(next_elem, doc)
                                    if title in next_p.text.strip():
                                        skip_elements.add(id(next_elem))
                        except ValueError:
                            pass

            # 查找段落内的 Drawing 图片（现代 Word 格式）
            drawings = para._element.findall('.//' + ns.qn('w:drawing'))
            for drawing in drawings:
                blip = drawing.find('.//' + ns.qn('a:blip'))
                if blip is not None:
                    rId = blip.get(ns.qn('r:embed'))
                    if rId:
                        has_image = True
                        # 读取 alt text
                        alt_text = None
                        docPr = drawing.find('.//' + ns.qn('wp:docPr'))
                        if docPr is not None:
                            alt_text = docPr.get('descr')
                            if alt_text:
                                alt_text = alt_text.strip()
                        process_image(rId, alt_text)

            # 查找段落内的 VML 图片（旧版 Word / 从网页粘贴的图片）
            picts = para._element.findall('.//' + ns.qn('w:pict'))
            for pict in picts:
                imagedata = pict.find('.//' + ns.qn('v:imagedata'))
                if imagedata is not None:
                    rId = imagedata.get(ns.qn('r:id'))
                    if rId:
                        has_image = True
                        # VML 图片的 alt text 在 v:shape 的 alt 属性中
                        alt_text = None
                        shape = pict.find('.//' + ns.qn('v:shape'))
                        if shape is not None:
                            alt_text = shape.get('alt')
                            if alt_text:
                                alt_text = alt_text.strip()
                        process_image(rId, alt_text)
            if has_image:
                # 图片行已添加，跳过此段落的文本（可能为空或只包含图片）
                continue

            # 如果没有图片，正常处理段落
            text = para.text.strip()
            if not text:
                # 空行 => 段落分隔
                md_lines.append("")
                continue

            # 检查是否为标题
            if para.style.name.startswith('Heading'):
                level = int(para.style.name.split()[-1])
                md_lines.append(f"{'#' * level} {text}")
            else:
                # 普通段落，保留粗体斜体等简单格式
                # 这里简化处理，复杂格式可自行扩展
                md_lines.append(text)

        elif child.tag == ns.qn('w:tbl'):
            # 表格处理
            table = Table(child, doc)
            # 转换为 Markdown 表格
            rows = table.rows
            if not rows:
                continue
            # 表头（假设第一行为表头）
            header_cells = [cell.text.replace('\n', ' ') for cell in rows[0].cells]
            md_lines.append('| ' + ' | '.join(header_cells) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(header_cells)) + ' |')
            for row in rows[1:]:
                cells = [cell.text.replace('\n', ' ') for cell in row.cells]
                md_lines.append('| ' + ' | '.join(cells) + ' |')
            md_lines.append("")  # 表格后空行

    # 清理未被引用的临时图片文件
    for rId, fname in image_map.items():
        if rId not in used_rIds:
            temp_path = os.path.join(output_dir, fname)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # 写入 Markdown 文件
    input_name = Path(docx_path).stem
    md_path = os.path.join(output_dir, f"{input_name}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"Markdown 已生成：{md_path}")
    return md_path


# ---------- PDF 转换部分 ----------
def _is_bold_font(font_name):
    """判断字体名是否为粗体"""
    bold_keywords = ['bold', 'black', 'heavy', 'demi', 'medium']
    name_lower = font_name.lower()
    return any(kw in name_lower for kw in bold_keywords)


def _merge_para_lines(lines):
    """将同一段落的多行合并为一个文本块字典"""
    if not lines:
        return None
    if len(lines) == 1:
        l = lines[0]
        return {
            "text": l["text"],
            "bbox": l["bbox"],
            "size": l["size"],
            "font": l["font"],
            "bold": l["bold"],
            "is_caption": False,
        }
    # 合并文本（行间用空格连接）
    merged_text = " ".join(l["text"] for l in lines)
    # 合并 bbox：取所有行的外接矩形
    x0 = min(l["bbox"][0] for l in lines)
    y0 = min(l["bbox"][1] for l in lines)
    x1 = max(l["bbox"][2] for l in lines)
    y1 = max(l["bbox"][3] for l in lines)
    # 取第一行的字体大小和字体名（标题行通常第一行就决定了）
    first = lines[0]
    return {
        "text": merged_text,
        "bbox": [x0, y0, x1, y1],
        "size": first["size"],
        "font": first["font"],
        "bold": first["bold"],
        "is_caption": False,
    }


def pdf_to_markdown(pdf_path, output_dir):
    """将 PDF 转为 Markdown，提取图片并以图注命名"""
    doc = fitz.open(pdf_path)
    md_lines = []
    img_counter = 0

    for page_num, page in enumerate(doc, start=1):
        # 1. 提取文本行（保留位置、字体信息）
        blocks = page.get_text("dict")["blocks"]
        text_lines = []
        for b in blocks:
            if b["type"] == 0:  # 文本块
                for line in b["lines"]:
                    text = "".join([span["text"] for span in line["spans"]])
                    if text.strip():
                        text_lines.append({
                            "text": text.strip(),
                            "bbox": list(line["bbox"]),
                            "size": max(span["size"] for span in line["spans"]),
                            "font": line["spans"][0]["font"],
                            "bold": any(_is_bold_font(span["font"]) for span in line["spans"]),
                        })
        text_lines.sort(key=lambda tb: (tb["bbox"][1], tb["bbox"][0]))

        # 2. 将相邻文本行合并为段落（Y 间距小、左边界接近的行属于同一段）
        text_blocks = []
        if text_lines:
            current_para = [text_lines[0]]
            for i in range(1, len(text_lines)):
                prev = text_lines[i - 1]
                curr = text_lines[i]
                # 同一段落：行间距小且左边界接近
                if (curr["bbox"][1] - prev["bbox"][3]) < 10 and abs(curr["bbox"][0] - prev["bbox"][0]) < 20:
                    current_para.append(curr)
                else:
                    text_blocks.append(_merge_para_lines(current_para))
                    current_para = [curr]
            text_blocks.append(_merge_para_lines(current_para))

        # 3. 提取图片信息
        image_infos = []
        img_list = page.get_images(full=True)
        for img_index, img in enumerate(img_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]
            try:
                bbox = page.get_image_bbox(img)
            except Exception:
                bbox = None
            image_infos.append({
                "xref": xref,
                "bytes": image_bytes,
                "ext": ext,
                "bbox": bbox,
                "caption": None,
            })

        # 4. 为图片匹配题注（用 is_caption 标记，避免文本匹配误删）
        # 优先匹配图片下方，其次匹配图片上方
        for info in image_infos:
            bbox = info["bbox"]
            if bbox:
                img_bottom = bbox[3]
                img_top = bbox[1]
                img_x_center = (bbox[0] + bbox[2]) / 2
                caption_found = False
                # 先找图片下方
                for tb in text_blocks:
                    if tb["is_caption"]:
                        continue
                    tb_top = tb["bbox"][1]
                    tb_x_center = (tb["bbox"][0] + tb["bbox"][2]) / 2
                    if 0 < tb_top - img_bottom < 50 and abs(tb_x_center - img_x_center) < (bbox[2] - bbox[0]) * 0.6:
                        info["caption"] = tb["text"]
                        tb["is_caption"] = True
                        caption_found = True
                        break
                # 再找图片上方
                if not caption_found:
                    for tb in text_blocks:
                        if tb["is_caption"]:
                            continue
                        tb_bottom = tb["bbox"][3]
                        tb_x_center = (tb["bbox"][0] + tb["bbox"][2]) / 2
                        if 0 < img_top - tb_bottom < 50 and abs(tb_x_center - img_x_center) < (bbox[2] - bbox[0]) * 0.6:
                            info["caption"] = tb["text"]
                            tb["is_caption"] = True
                            break
            if not info["caption"]:
                img_counter += 1
                info["caption"] = f"图 {img_counter}"

        # 5. 将图片和文本统一排序，按 Y 坐标交错输出
        elements = []
        for tb in text_blocks:
            elements.append(("text", tb))
        for info in image_infos:
            if info["bbox"]:
                elements.append(("image", info, info["bbox"][1]))
            else:
                elements.append(("image", info, float('inf')))
        elements.sort(key=lambda e: e[2] if e[0] == "image" else e[1]["bbox"][1])

        # 6. 计算标题级别（基于字体大小分布）
        non_caption_blocks = [tb for tb in text_blocks if not tb["is_caption"]]
        if non_caption_blocks:
            from collections import Counter
            size_counts = Counter(tb["size"] for tb in non_caption_blocks)
            body_size = size_counts.most_common(1)[0][0]
            sizes = sorted(set(tb["size"] for tb in non_caption_blocks), reverse=True)
        else:
            body_size = 12
            sizes = []

        # 按字体大小降序分配 h1, h2, h3...（相邻字号差距>2pt才视为不同层级，避免断层）
        heading_sizes = [s for s in sizes if s > body_size + 1]
        heading_level_map = {}
        level = 1
        prev_s = None
        for s in heading_sizes[:6]:
            if prev_s is not None and (prev_s - s) <= 2:
                # 与上一级字号差距太小，归为同一层级
                heading_level_map[s] = heading_level_map[prev_s]
            else:
                heading_level_map[s] = level
                level += 1
            prev_s = s

        # 7. 按顺序输出
        for elem in elements:
            if elem[0] == "image":
                info = elem[1]
                caption = info["caption"]
                safe_cap = re.sub(r'[\\/*?:"<>|]', "", caption)
                new_name = f"{safe_cap}.{info['ext']}"
                new_path = os.path.join(output_dir, new_name)
                dup_counter = 1
                while os.path.exists(new_path):
                    base, ext = os.path.splitext(new_name)
                    new_name = f"{base}_p{page_num}_{dup_counter}.{ext}"
                    new_path = os.path.join(output_dir, new_name)
                    dup_counter += 1
                with open(new_path, "wb") as f:
                    f.write(info["bytes"])
                md_lines.append(f"![{caption}]({new_name})")
            else:
                tb = elem[1]
                # 跳过已作为题注的文本块
                if tb["is_caption"]:
                    continue
                text = tb["text"]
                size = tb["size"]
                # 判断标题级别
                level = heading_level_map.get(size)
                if level and (size > body_size + 1 or tb["bold"]):
                    md_lines.append(f"{'#' * level} {text}")
                else:
                    md_lines.append(text)
        md_lines.append("")  # 页面间分隔

    # 写入 Markdown
    input_name = Path(pdf_path).stem
    md_path = os.path.join(output_dir, f"{input_name}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"Markdown 已生成：{md_path}")
    return md_path


# ---------- GUI ----------
def launch_gui():
    """启动 tkinter GUI 界面"""
    import tkinter as tk
    from tkinter import filedialog, scrolledtext, messagebox
    import threading

    root = tk.Tk()
    root.title("Doc2MD — Word/PDF 转 Markdown")
    root.resizable(True, True)
    root.minsize(520, 380)

    # 输入文件
    tk.Label(root, text="输入文件：").grid(row=0, column=0, sticky="e", padx=(10, 4), pady=8)
    input_var = tk.StringVar()
    input_entry = tk.Entry(root, textvariable=input_var, width=48)
    input_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

    def browse_input():
        path = filedialog.askopenfilename(
            title="选择 Word 或 PDF 文件",
            filetypes=[("支持的文件", "*.docx *.pdf"), ("Word 文档", "*.docx"), ("PDF 文件", "*.pdf")]
        )
        if path:
            input_var.set(path)
            # 自动填充输出目录为输入文件所在目录
            if not output_var.get():
                output_var.set(os.path.dirname(os.path.abspath(path)))

    tk.Button(root, text="浏览...", command=browse_input, width=6).grid(row=0, column=2, padx=(4, 10), pady=8)

    # 输出目录
    tk.Label(root, text="输出目录：").grid(row=1, column=0, sticky="e", padx=(10, 4), pady=8)
    output_var = tk.StringVar()
    output_entry = tk.Entry(root, textvariable=output_var, width=48)
    output_entry.grid(row=1, column=1, padx=4, pady=8, sticky="ew")
    # 灰色提示文字
    output_placeholder = "留空则同输入文件目录"
    output_entry.insert(0, output_placeholder)
    output_entry.config(fg="grey")
    output_entry.bind("<FocusIn>", lambda e: (
        output_entry.delete(0, tk.END) if output_var.get() == output_placeholder else None,
        output_entry.config(fg="black") if output_entry.cget("fg") == "grey" else None
    ))
    output_entry.bind("<FocusOut>", lambda e: (
        (output_entry.insert(0, output_placeholder), output_entry.config(fg="grey"))
        if not output_var.get() else None
    ))

    def browse_output():
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            output_var.set(path)

    tk.Button(root, text="浏览...", command=browse_output, width=6).grid(row=1, column=2, padx=(4, 10), pady=8)

    # 日志区域
    log_box = scrolledtext.ScrolledText(root, height=14, width=60, state="disabled", font=("Consolas", 9))
    log_box.grid(row=2, column=0, columnspan=3, padx=10, pady=(4, 8), sticky="nsew")

    def log(msg):
        """向日志框追加一行文本（线程安全，通过 root.after 推回主线程执行）"""
        def _write():
            log_box.config(state="normal")
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
            log_box.config(state="disabled")
        root.after(0, _write)

    # 转换按钮
    converting = [False]  # 用列表包装以便在闭包中修改

    def do_convert():
        if converting[0]:
            return
        input_path = input_var.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请选择输入文件")
            return
        if not os.path.exists(input_path):
            messagebox.showerror("错误", f"文件不存在：\n{input_path}")
            return

        ext = Path(input_path).suffix.lower()
        if ext not in ('.docx', '.pdf'):
            messagebox.showerror("错误", "仅支持 .docx 和 .pdf 文件")
            return

        output_dir = output_var.get().strip()
        if output_dir == output_placeholder:
            output_dir = ""
        output_dir = output_dir or os.path.dirname(os.path.abspath(input_path))
        os.makedirs(output_dir, exist_ok=True)

        converting[0] = True
        convert_btn.config(state="disabled")
        log(f"正在转换：{input_path}")

        def run():
            try:
                # 重定向 print 输出到日志框
                import io
                import contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    if ext == '.docx':
                        result = docx_to_markdown(input_path, output_dir)
                    else:
                        result = pdf_to_markdown(input_path, output_dir)
                # 输出捕获的 print 内容
                for line in buf.getvalue().splitlines():
                    log(line)
                log("转换完成！")
                root.after(0, lambda: messagebox.showinfo("完成", f"转换成功！\n输出目录：{output_dir}"))
            except Exception as ex:
                log(f"错误：{ex}")
                root.after(0, lambda err=ex: messagebox.showerror("错误", f"转换失败：{err}"))
            finally:
                converting[0] = False
                root.after(0, lambda: convert_btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    convert_btn = tk.Button(root, text="转换", command=do_convert, width=12, font=("", 10, "bold"))
    convert_btn.grid(row=3, column=0, columnspan=3, pady=(0, 10))

    # 让中间列随窗口拉伸
    root.columnconfigure(1, weight=1)
    root.rowconfigure(2, weight=1)

    root.mainloop()


# ---------- 主流程 ----------
def main():
    # 无命令行参数时启动 GUI
    if len(sys.argv) == 1:
        launch_gui()
        return

    parser = argparse.ArgumentParser(
        description="将 Word/PDF 论文转为 Markdown，图片自动保存并以图注命名。无参数启动时将打开图形界面。"
    )
    parser.add_argument("input", help="输入的 .docx 或 .pdf 文件路径")
    parser.add_argument("-o", "--output-dir", default=None, help="输出目录，默认为输入文件所在目录")
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"错误：文件不存在 - {input_path}")
        sys.exit(1)

    output_dir = args.output_dir or os.path.dirname(os.path.abspath(input_path))
    os.makedirs(output_dir, exist_ok=True)

    ext = Path(input_path).suffix.lower()
    if ext == '.docx':
        docx_to_markdown(input_path, output_dir)
    elif ext == '.pdf':
        pdf_to_markdown(input_path, output_dir)
    else:
        print("目前只支持 .docx 和 .pdf 文件")
        sys.exit(1)


if __name__ == "__main__":
    main()