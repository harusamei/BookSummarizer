from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak)
from reportlab.platypus import Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle


class PDFSaver:
    def __init__(self):
        
        # 注册中文字体
        pdfmetrics.registerFont(TTFont('SimSun', 'simsun.ttc'))
        self.set_style()
        self.doc = None
        self.elements = []

    def set_style(self):
        # 默认样式
        styles = getSampleStyleSheet()
        # 自定义样式
        self.title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontName='SimSun',
            fontSize=22,
            leading=18,
            alignment=1,  # 居中
            spaceAfter=20,
        )
        self.heading1_style = ParagraphStyle(
            'Heading1',
            parent=styles['Heading1'],
            fontName='SimSun',
            fontSize=18,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
        )
        self.heading2_style = ParagraphStyle(
            'Heading2',
            parent=styles['Heading1'],
            fontName='SimSun',
            fontSize=14,
            leading=16,
            spaceBefore=12,
            spaceAfter=8,
        )
        self.body_style = ParagraphStyle(
            'BodyText',
            parent=styles['BodyText'],
            fontName='SimSun',
            fontSize=12,
            leading=16,
            spaceAfter=10,
        )
        self.cell_style = ParagraphStyle(
            name="TableCell",
            fontName="SimSun",
            fontSize=10,
            leading=12,
            wordWrap='CJK',  # 启用中文自动换行
        )
    
    def create_pdf(self, filename="output.pdf"):

        doc = SimpleDocTemplate(
            filename,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=108,
            bottomMargin=72,
        )
        # 页面模板，添加页眉页脚
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )
        template = PageTemplate(id='with_header_footer', frames=frame, onPage= self.header_footer)
        doc.addPageTemplates([template])
        self.doc = doc

    def header_footer(self, canvas, doc):
        # 页眉
        canvas.saveState()
        canvas.setFont('SimSun', 10)
        canvas.drawString(inch, letter[1] - 0.75 * inch, "~八分钟读书推荐@书甜~")
        # 页脚
        canvas.setFont('SimSun', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(inch, 0.75 * inch, f"第 {doc.page} 页")
        canvas.restoreState()

    def add_page_break(self):
        """
        添加分页符
        """
        self.elements.append(PageBreak())

    def add_title(self, title: str):
        # Title
        self.elements.append(Paragraph(title, self.title_style))
        self.elements.append(Spacer(1, 0.2*inch))

    def add_heading1(self, heading: str):
        # 一级标题
        self.elements.append(Paragraph(heading, self.heading1_style))
        self.elements.append(Spacer(1, 0.1*inch))

    def add_heading2(self, heading: str):
        # 二级标题
        self.elements.append(Paragraph(heading, self.heading2_style))
        #self.elements.append(Spacer(1, 0.2*inch))

    # 加多行内容
    def add_body(self, content: list[str]):
        # 正文
        for body_txt in content:
            self.elements.append(Paragraph(body_txt, self.body_style))
            #self.elements.append(Spacer(1, 0.1*inch))

    def add_table(self, data: list[list], col_widths=None, row_heights=None):
        # 将数据转换为 Paragraph 对象
        wrapped_data = [
            [Paragraph(str(cell), self.cell_style) for cell in row]
            for row in data
        ]
        # 创建表格
        table = Table(wrapped_data, colWidths=col_widths, rowHeights= row_heights)

        # 定义表格样式
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # 表头背景色
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # 表头文字颜色
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # 居中对齐
            ('FONTNAME', (0, 0), (-1, 0), 'SimSun'),  # 表头字体
             ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),  # 表主体字体
            ('FONTSIZE', (0, 0), (-1, -1), 10),  # 字体大小
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # 表头底部填充
            #('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # 表格背景色
            ('GRID', (0, 0), (-1, -1), 1, colors.black),  # 表格边框
        ])
        table.setStyle(style)

        # 添加表格到元素列表
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.5 * inch))  # 添加间距

    def save(self):
        self.doc.build(self.elements)

if __name__ == '__main__':

    pdf_saver = PDFSaver()
    pdf_saver.create_pdf(filename="test.pdf")
    pdf_saver.add_title("中文标题")
    pdf_saver.add_heading1("一级标题")
    pdf_saver.add_heading2("二级标题")
    pdf_saver.add_body(["This is some content to save in the PDF."])
    data = [
        ["列1", "列2", "列3"],
        ["数据1", "数据2", "数据3"],
        ["数据4", "数据5", "数据6"],
    ]
    pdf_saver.add_table(data, col_widths=[1.5*inch, 1.5*inch, 1.5*inch], row_heights=[0.5*inch]*len(data))
    pdf_saver.save()
    print("PDF saved successfully.")
