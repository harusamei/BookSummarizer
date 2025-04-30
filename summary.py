# 生成用于文字版和视频版的文档
####################################################
import sys
import os
import asyncio
import json
import pandas as pd
import copy
from LLM.prompt_loader1 import Prompt_generator
from LLM.llm_agent import LLMAgent
from LLM.ans_extractor import AnsExtractor
from processor import DProcessor
from pdfsaver import PDFSaver
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle


sys.path.insert(0, os.getcwd().lower())


class BookSummary:
    def __init__(self, language='Chinese'):

        self.prompter = Prompt_generator()
        self.ans_extr = AnsExtractor()
        self.llm = LLMAgent()
        self.dp = DProcessor()      # data processor
        self.pdf_saver = PDFSaver()
        self.lang = language
        # 文件使用的扩展名
        self.exts = {
            'bookInfo': '.json',
            'introduction': '_std.md',      # 文字版导言
            'voiceover': '_bv.md',        # B站视频旁白
            'visualDesc': '_desc.json',     # 图像，视频描述
            'official': '_intro.txt',       # 官方或书籍序言
            'videoStructure': '_vid.json'   # 视频结构
        }
        self.flags = {}

    async def gen_batch(self, xls_file):
        books = pd.read_excel(xls_file, sheet_name=0)
        books.columns = books.columns.str.strip()  # 去除列名中的多余空格
        books.fillna(inplace=True, value='')
        book_dir = os.path.dirname(os.path.abspath(xls_file))
        
        for _, row in books.iterrows():
            hasWritten, hasIntroduction = False, False
            self.flags = {}
            title = row['title']
            if title.startswith('《'):
                title = title[1:-1]
            author = row['author']
            # 有书籍序言或专业导读
            hasIntroduction = row['hasReference']
            # 写好的2000字导读
            hasWritten = row['hasWritten']
            if hasWritten.lower() == 'y':
                hasWritten = True
            if hasIntroduction.lower() == 'y':
                hasIntroduction = True
            # 创建以书名命名的目录
            sub_book_dir = os.path.join(book_dir, title)
            if not os.path.exists(sub_book_dir):
                os.makedirs(sub_book_dir)
            data_dir = os.path.join(sub_book_dir, 'data')
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            # print(f'author: {author}, title: {title}')
            # self.flags['bookInfo'] = await self.gen_bookInfo(title, author, data_dir)

            # print('part 1: generate book summarization')
            # # 有人工写的导读
            # if hasWritten is True:
            #     print(f"Book {title} already has a human-written.")
            # elif hasIntroduction is True:   # 书籍序言或专业导读
            #     print(f"Book {title} already has an official introduction .")
            #     self.flags['introduction'] = await self.rewrite_intro(title, author, data_dir)
            # else:
            #     self.flags['introduction'] = await self.gen_introduction(title, author, data_dir)
            # print('part 2: generate visual content')
            # tryCount = 0
            # while self.flags.get('videoStructure',False) is False and tryCount < 1:
            #     self.flags['videoStructure'] = await self.gen_videoStructure(title, data_dir)
            #     tryCount += 1
            self.flags['videoStructure'] = True
            self.flags['visualDesc'] = True
            # tryCount = 0
            # while self.flags.get('visualDesc',False) is False and tryCount < 1:
            #     self.flags['visualDesc'] = await self.gen_visualDesc(title, data_dir)
            #     tryCount += 1
            # self.flags['imgPrompt'] = await self.gen_imgPrompt(title, data_dir)
            # print('part 3: generate voiceover script')
            # self.flags['voiceover'] = await self.gen_voiceover(title, author, data_dir)

            await self.pdf_output(title, sub_book_dir)
            break
    
    # 输出json 存放在book_dir 目录下
    async def gen_bookInfo(self, title, author, book_dir):

        tmpls = {}
        tasks = ['brief_intro', 'key_scenes']
        for key in tasks:
            tmpls[key] = self.prompter.tasks[key]

        abook = {}
        for key in tasks:
            print(f"gen {key} for {title}")
            query = tmpls[key].format(title=title, author=author, language=self.lang)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr(key, asw)
            if result['status'] == 'failed':
                print(f"Failed to generate {key} for {title}")
                return False
            result = result['msg']
            abook.update(result)

        ext = self.exts['bookInfo']
        outFile = os.path.join(book_dir, f'{title}{ext}')
        self.dp.save_json(outFile, abook)
        return True

    async def gen_introduction(self, title, author, book_dir):
        
        abook = {}
        tmpl = self.prompter.tasks['book_introduction']
        if self.flags.get('bookInfo') is False:
            abook['author'] = author
            abook['title'] = title
        else:
            ext = self.exts['bookInfo']
            with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
                abook = json.load(f)
        
        jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
        query = tmpl.format(book_info=jsonStr)
        asw = await self.llm.ask_llm(query, '')
        ext = self.exts['introduction']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)

        return True
    
    async def rewrite_intro(self, title, author, book_dir):
        print(f"rewrite intro for {title}")
        tmpl = self.prompter.tasks['intro_rewrite']
        if self.flags.get('bookInfo') is True:
            ext = self.exts['bookInfo']
            with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
                abook = json.load(f)
        else:
            abook = {}
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        ext = self.exts['official']
        filePath = os.path.join(book_dir, f'{title}{ext}')
        if os.path.exists(filePath):
            with open(filePath, 'r', encoding='utf-8') as f:
                oguide = f.read()
        else:
            print(f"Failed to load {title}{ext} in rewrite_intro.")
            return False
        
        query = tmpl.format(book_info=bookInfo, intro_txt=oguide)
        
        asw = await self.llm.ask_llm(query, '')
        ext = self.exts['introduction']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)

        return True
    
    # B站视频旁白
    async def gen_voiceover(self, title, author, book_dir, total_word=1800):
        
        if self.flags['videoStructure'] is False or self.flags['introduction'] is False:
            print(f"Failed to generate voicevoer for {title}")
            return False
        
        tmpl = self.prompter.tasks['b_voiceover']
        ext = self.exts['videoStructure']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        vid.pop('overall_style', None)
        item = vid['cover_image']
        item.pop('color_scheme', None)
        total_minutes = sum([i['duration'] for i in vid['video_structure']])
        
        for item in vid['video_structure']:
            item.pop('thumbnail_concept', None)
            item.pop('music_style', None)
            item.pop('visual_style', None)
            item.pop('motion_graphics', None)
            item.pop('scene_description', None)
            duration = item['duration']
            wcount = int(duration / total_minutes*total_word/50)*50
            item['word_count'] = wcount
            item.pop('duration', None)
        vid_stru = json.dumps(vid, ensure_ascii=False, indent=4)
        ext = self.exts['introduction']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        query = tmpl.format(word_count=total_word,vid_stru=vid_stru, std_txt=intro_txt)
        with open('temp_query.txt', 'w', encoding='utf-8') as f:
            f.write(query)
        asw = await self.llm.ask_llm(query, '')

        ext = self.exts['voiceover']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)
        return True
        
    # 基于文字版intro+bookinfo 生成视频结构
    async def gen_videoStructure(self, title, book_dir, minutes=5):
        print(f"gen_videoStructure for {title}")

        tmpl = self.prompter.tasks['visual_designer']
        if self.flags.get('bookInfo') is True:
            ext = self.exts['bookInfo']
            with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
                abook = json.load(f)
        else:
            abook = {}
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        if self.flags['introduction'] is False:
            print('no introduction to gen videoStructure for {title}')
            return False
        
        ext = self.exts['introduction']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        
        query = tmpl.format(minutes=minutes, std_txt=intro_txt, book_info=bookInfo)
        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('visual_designer', asw)
        if result['status'] == 'failed':
            print(f"Failed to generate video structure for {title}")
            return False
        result = result['msg']
        ext = self.exts['videoStructure']
        self.dp.save_json(os.path.join(book_dir, f'{title}{ext}'), result)
        return True
    
    async def gen_visualDesc(self, title, book_dir):
        print(f"gen_visualDesc for {title}")
        if self.flags['videoStructure'] is False:
            print(f"failed becaused of missing videoStructure")
            return False
        
        tmpl = self.prompter.tasks['visual_desc2']
        ext = self.exts['videoStructure']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        secs = vid['video_structure']
        overall_style = vid['overall_style']
        allDesc = []
        for indx, sec in enumerate(secs):
            print(f"sec: {sec['segment']}")
            wight = 5
            if indx == 0:
                wight = 6
            elif indx == len(secs)-1:
                wight = 4
            count = sec['duration']*wight
            sec['overall_style'] = overall_style
            sec.pop('music_style', None)
            vidInfo = json.dumps(sec, ensure_ascii=False, indent=4)
            query = tmpl.format(vid_stru=vidInfo, count=count)
            with open('temp_query.txt', 'w', encoding='utf-8') as f:
                f.write(query)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('visual_desc2', asw)
            if result['status'] == 'failed':
                print(f"Failed to generate visual desc for {sec['segment']}")
                print(f"asw: {asw}")
                return False
            
            result = result['msg']
            shots = [{'section': sec['segment'], **shot} for shot in result['shots']]
            allDesc.extend(shots)

        for i, item in enumerate(allDesc):
            item['shot_number'] = i+1
        newDesc = copy.deepcopy(allDesc)
        for item in newDesc:
            item.pop('section', None)
            item.pop('motion_graphic', None)
        
        print(f"group_reusedImage for {title}")
        tmpl = self.prompter.tasks['reused_image']
        
        vidInfo = json.dumps({'shots': newDesc}, ensure_ascii=False, indent=4)
        query = tmpl.format(img_desc=vidInfo)
        # with open('temp_query.txt', 'w', encoding='utf-8') as f:
        #     f.write(query)

        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('reused_image', asw)
        if result['status'] == 'failed':
            print(f"Failed to generate video structure for {title}")
            return False
        result = result['msg']
        
        for group in result['reused_images']:
            reused = group['shots']
            reused.sort()
            baseId = reused[0]
            for sId in reused[1:]:
                allDesc[sId-1]['reused'] = f'shot_number_{baseId}'

        ext = self.exts['visualDesc']
        self.dp.save_json(os.path.join(book_dir, f'{title}{ext}'), {'shots': allDesc})
        return True

    async def gen_imgPrompt(self, title, book_dir):
        print(f"gen_imgPrompt for {title}")
        if self.flags['visualDesc'] is False:
            print(f"failed becaused of missing visualDesc")
            return False
        
        tmpl = self.prompter.tasks['img_prompt']
        ext = self.exts['visualDesc']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        for item in vid['shots']:
            print(f"gen image prompt for shot: {item['shot_number']}")
            stFrame = item['static_frame']
            sfInfo = json.dumps(stFrame, ensure_ascii=False, indent=4)
            query = tmpl.format(static_frame=sfInfo)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('img_prompt', asw)
            if result['status'] == 'failed':
                print(f"Failed to generate image prompt for {title}")
                return False
            item['img_prompt'] = result['msg']
            
        ext = self.exts['visualDesc']
        self.dp.save_json(os.path.join(book_dir, f'{title}{ext}'), vid)
        return True
    # 翻译为中文，并保存为pdf
    async def pdf_output(self, title, book_dir):
        print(f"output PDF document for {title}")

        ext = self.exts['visualDesc']
        with open(os.path.join(book_dir, f'data/{title}{ext}'), 'r', encoding='utf-8') as f:
            vds = json.load(f)

        secs = []
        secName = ''
        tSec = []
        for shot in vds['shots']:
            if secName != shot['section']:
                secs.append(tSec)
                tSec = [shot]
                secName = shot['section']
                print(f"section: {shot['section']}, shot_number: {shot['shot_number']}")
            else:
                tSec.append(shot)
        if len(tSec) > 0:
            secs.append(tSec)
        secs = secs[1:]
        ext = self.exts['videoStructure']
        with open(os.path.join(book_dir, f'data/{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        
        self.pdf_saver.create_pdf(filename=os.path.join(book_dir, f'{title}_cn.pdf'))
        self.pdf_saver.add_title(f"视频大纲：{title}")
        self.pdf_saver.add_body([f"整体风格：{'; '.join(vid['overall_style'])}"])
        cover = vid['cover_image']
        contents = [f"标题  ： {cover['title']}",
                   f"副标题 ： {cover['subtitle']}",
                   f"封面构图：{cover['composition']}",
                   f"封面色调：{cover['color_scheme']}",
                   "-----------------------------------"
        ]
        self.pdf_saver.add_body(contents)
        for i, item in enumerate(vid['video_structure']):
            self.pdf_saver.add_heading1(f"{item['segment']}")
            contents =[f"段标题：{item['tagline']}",
                       f"时长：{item['duration']}秒",
                       f"概念图：{item['thumbnail_concept']}",
                       f"音乐：{item['music_style']}",
                       f"视频风格：{item['visual_style']}",
                       f"场景：{item['scene_description']}",
                       f"动图：{item['motion_graphics']}",
                       f"镜头个数：{len(secs[i])}个"
            ]
            self.pdf_saver.add_body(contents)
            tbody = [["No.", "简述", "复用"]]
            for shot in secs[i]:
                reused = shot.get('reused', '')
                reused = reused.replace('shot_number_', 'No_')
                tbody.append([shot['shot_number'], shot['shot_title'], reused])
            self.pdf_saver.add_table(tbody, col_widths=[1*inch, 3*inch, 1*inch])

        self.pdf_saver.add_page_break()
        self.pdf_saver.add_heading1(f"生图提示词：")
        self.pdf_saver.cell_style = ParagraphStyle(
            name="TableCell",
            fontName="SimSun",
            fontSize=8,
            leading=12,
            wordWrap='CJK',  # 启用中文自动换行
        )
        tbody = [["Sect.","Shot", "Prompt"]]
        for i, shots in enumerate(secs):
            for shot in shots:
                shot_num = shot['shot_number']
                prompt = shot['img_prompt']
                tbody.append([i+1, shot_num, prompt['prompt_cn']])
        self.pdf_saver.add_table(tbody, col_widths=[0.5*inch, 0.5*inch, 6*inch])
        self.pdf_saver.save()
        return

        
if __name__ == '__main__':

    out_path ='books'
    wk_dir = os.getcwd()
    directory = os.path.join(wk_dir, out_path)
    xls_file = os.path.join(directory, 'booklist.xlsx')
    print(f"xls_file: {xls_file}")
    bs = BookSummary()
    asyncio.run(bs.gen_batch(xls_file))

    print("Done!")