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

config = {
    'language': 'Chinese',
    'duration': 5,              # 视频时长
    'img_count': 5,             # 每秒生成的图片数量
    'voice_word': 250*5,        # 旁白字数, 每分钟250字
    'txt_word': 500*5,          # 文字版字数
}


class BookSummary:
    def __init__(self):

        self.prompter = Prompt_generator()
        self.ans_extr = AnsExtractor()
        self.llm = LLMAgent()
        self.dp = DProcessor()      # data processor
        self.pdf_saver = PDFSaver()
        self.lang = config['language']  # 语言
        self.duration = config['duration']  # 视频时长
        self.voice_word = config['voice_word']  # 旁白字数
        self.img_count = config['img_count']  # 每秒生成的图片数量
        # 文件使用的扩展名
        self.exts = {
            'bookInfo': '.json',
            'introduction': '_std.md',      # 文字版导言
            'voiceover': '_bv.md',          # B站视频旁白
            'visualDesc': '_desc.json',     # 图像，视频描述
            'reference': '_ref.txt',        # 书籍序言或专业导读
            'videoDesign': '_vid.json'      # 视频结构
        }
        self.flags = {}                     # 每一步成功与否的标志
        self.resetFlags()

    def resetFlags(self):
        self.flags = {}
        for key in ['reference','bookInfo', 'introduction', 'videoDesign', 'visualDesc', 'voiceover']:
            self.flags[key] = False

    def init(self, row, book_dir):

        self.resetFlags()
        title = row['title'].lower()
        if title.startswith('《'):
            title = title[1:-1]
        hasData = False
        # 创建以书名命名的目录
        bname_dir = os.path.join(book_dir, title)
        if not os.path.exists(bname_dir):
            os.makedirs(bname_dir)
        data_dir = os.path.join(bname_dir, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        else:
            hasData = True
        
        if hasData is False:
            return title, bname_dir
        
        # 目录已经存在，检查是否有数据文件
        for key, ext in self.exts.items():
            file = os.path.join(data_dir, f'{title}{ext}')
            if os.path.exists(file):
                self.flags[key] = True
        return title, bname_dir

    async def gen_batch(self, xls_file):
        books = pd.read_excel(xls_file, sheet_name=0)
        books.columns = books.columns.str.strip()  # 去除列名中的多余空格
        books.fillna(inplace=True, value='')
        book_dir = os.path.dirname(os.path.abspath(xls_file))
        
        for _, row in books.iterrows():
            
            title, bname_dir = self.init(row, book_dir)
            data_dir = os.path.join(bname_dir, 'data')
            author = row['author'].lower()
            print(f'author: {author}, title: {title}')
            self.flags['bookInfo'] = await self.gen_bookInfo(title, author, data_dir)
            # 生成文字版的导读
            print('part 1: generate txt summarization')
            self.flags['introduction'] = await self.rewrite_intro(title, author, data_dir)
            self.flags['introduction'] = await self.gen_introduction(title, author, data_dir)

            print('part 2: generate visual documents')
            self.flags['videoDesign'] = await self.gen_videoDesign(title, data_dir)
            self.flags['visualDesc'] = await self.gen_visualDesc(title, data_dir)
            self.flags['imgPrompt'] = await self.gen_imgPrompt(title, data_dir)

            print('part 3: generate voiceover script')
            self.flags['voiceover'] = await self.gen_voiceover(title, author, data_dir)

            # await self.pdf_output(title, bname_dir)
            break
    
    # 输出json 存放在store_dir
    async def gen_bookInfo(self, title, author, store_dir):

        if self.flags['bookInfo'] is True:
            print(f"bookInfo for {title} already exists")
            return True
        
        print(f"gen_bookInfo for {title}")
        tmpls = {}
        tasks = ['brief_intro', 'key_scenes']
        for key in tasks:
            tmpls[key] = self.prompter.tasks[key]
        abook = {}
        for key in tasks:
            query = tmpls[key].format(title=title, author=author, language=self.lang)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr(key, asw)
            if result['status'] == 'failed':
                print(f"Failed to generate {key} for {title}")
                return False
            result = result['msg']
            abook.update(result)

        ext = self.exts['bookInfo']
        outFile = os.path.join(store_dir, f'{title}{ext}')
        self.dp.save_json(outFile, abook)
        return True

    async def gen_introduction(self, title, author, data_dir):
        # 已经存在文字版导读
        if self.flags['introduction'] is True:
            print(f"introduction for {title} already exists")
            return True
        
        print(f"gen introduction for {title}")
        abook = {}
        tmpl = self.prompter.tasks['book_introduction']
        if self.flags['bookInfo'] is False:
            abook['author'] = author
            abook['title'] = title
        else:
            ext = self.exts['bookInfo']
            with open(os.path.join(data_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
                abook = json.load(f)
        
        jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
        query = tmpl.format(book_info=jsonStr)

        ext = self.exts['introduction']
        tryCount = 0
        flag = False
        # 生成3个导读
        while tryCount < 3:
            asw = await self.llm.ask_llm(query, '')
            tryCount += 1
            if len(asw) > 0 and 'err_llm:' not in asw:
                flag = True
                break 
        if flag is False:
            print(f"Failed to generate introduction for {title}")
        else:
            self.dp.save_txt(os.path.join(data_dir, f'{title}{ext}'), asw)
        return flag
    
    async def rewrite_intro(self, title, author, data_dir):
        if self.flags['introduction'] is True:
            print(f"introduction for {title} already exists")
            return True
        
        print(f"rewrite intro for {title}")

        ext = self.exts['reference']
        fileRef = os.path.join(data_dir, f'{title}{ext}')
        if self.flags['reference'] is False or not os.path.exists(fileRef):
            print(f"no reference to rewrite intro for {title}")
            return False
        
        tmpl = self.prompter.tasks['intro_rewrite']
        with open(fileRef, 'r', encoding='utf-8') as f:
            refData = f.read()

        if self.flags.get('bookInfo') is True:
            ext = self.exts['bookInfo']
            with open(os.path.join(data_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
                abook = json.load(f)
        else:
            abook = {}
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        query = tmpl.format(book_info=bookInfo, intro_txt=refData)
        ext = self.exts['introduction']
        tryCount = 0
        flag = False
        # 如失败尝试3次
        while tryCount < 3:
            asw = await self.llm.ask_llm(query, '')
            tryCount += 1
            if len(asw) > 0 and 'err_llm:' not in asw:
                flag = True
                break
        
        if flag is False:
            print(f"Failed to generate introduction for {title}")
        else:
            self.dp.save_txt(os.path.join(data_dir, f'{title}{ext}'), asw)
        return flag
    
    # B站视频旁白
    async def gen_voiceover(self, title, author, book_dir, total_word=1800):
        
        total_word = self.voice_word

        if self.flags['videoDesign'] is False or self.flags['introduction'] is False:
            print(f"no videoDesign or introduction to gen voicevoer for {title}")
            return False
        
        tmpl = self.prompter.tasks['b_voiceover']
        ext = self.exts['videoDesign']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        vid.pop('overall_style', None)
        item = vid['cover_image']
        item.pop('color_scheme', None)
        total_minutes = sum([i['duration'] for i in vid['video_structure']])
        print(f"total_minutes: {total_minutes}, config: {self.duration}")

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
    async def gen_videoDesign(self, title, data_dir):
        print(f"gen_videoDesign for {title}")
        if self.flags['videoDesign'] is True:
            print(f"videoDesign for {title} already exists")
            return True
        
        ext = self.exts['introduction']
        introFile = os.path.join(data_dir, f'{title}{ext}')
        ext = self.exts['bookInfo']
        binfoFile = os.path.join(data_dir, f'{title}{ext}')
        if self.flags['introduction'] is False:
            print(f"no introduction to gen videoDesign for {title}")
            return False
        if self.flags['bookInfo'] is False:
            print(f"no bookInfo to gen videoDesign for {title}")
            return False
        
        tmpl = self.prompter.tasks['visual_designer']
        with open(binfoFile, 'r', encoding='utf-8') as f:
            abook = json.load(f)
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)
        with open(introFile, 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        query = tmpl.format(minutes=self.duration, std_txt=intro_txt, book_info=bookInfo)

        ext = self.exts['videoDesign']
        tryCount = 0
        flag = False
        # 尝试3次生成视频结构
        while tryCount < 3:
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('visual_designer', asw)
            tryCount += 1
            if result['status'] == 'succ':
                flag = True
                break
        if flag is False:
            print(f"Failed to generate video structure for {title}")
            return False
        result = result['msg']
        self.dp.save_json(os.path.join(data_dir, f'{title}{ext}'), result)
        return True
    
    async def gen_visualDesc(self, title, book_dir):
        print(f"gen_visualDesc for {title}")
        if self.flags['visualDesc'] is True:
            print(f"visualDesc for {title} already exists")
            return True
        
        if self.flags['videoDesign'] is False:
            print(f"failed becaused of missing videoDesign")
            return False
        
        tmpl = self.prompter.tasks['visual_desc2']
        ext = self.exts['videoDesign']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        secs = vid['video_structure']
        overall_style = vid['overall_style']
        allDesc = []
        indx, tryCount = 0, 0
        while indx < len(secs) and tryCount < 3:
            sec = secs[indx]
            print(f"sec: {sec['segment']}")
            count = int(sec['duration']*self.img_count)
            sec['overall_style'] = overall_style
            sec.pop('music_style', None)
            vidInfo = json.dumps(sec, ensure_ascii=False, indent=4)
            query = tmpl.format(vid_stru=vidInfo, count=count)
            # with open('temp_query.txt', 'w', encoding='utf-8') as f:
            #     f.write(query)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('visual_desc2', asw)
            if result['status'] == 'failed':
                print(f"Failed to generate visual desc for {sec['segment']}")
                print(f"asw: {asw}")
                tryCount += 1
                continue
            
            result = result['msg']
            shots = [{'section': sec['segment'], **shot} for shot in result['shots']]
            allDesc.extend(shots)
            indx += 1

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
            result['reused_images'] = []
            print(f"Failed to group reused images for {title}")
        else:
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
        
        item = vid['shots'][0]
        if 'img_prompt' in item:
            print(f"img_prompt for {title} already exists")
            return True
        
        indx, tryCount = 0, 0
        while indx < len(vid['shots']) and tryCount < 3:
            item = vid['shots'][indx]
            print(f"gen image prompt for shot: {item['shot_number']}")
            stFrame = item['static_frame']
            sfInfo = json.dumps(stFrame, ensure_ascii=False, indent=4)
            query = tmpl.format(static_frame=sfInfo)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('img_prompt', asw)
            if result['status'] == 'failed':
                tryCount += 1
                print(f"Failed to generate image prompt for {item['shot_number']}")
                continue
            item['img_prompt'] = result['msg']
            indx += 1

        if indx < len(vid['shots']):
            print(f"Failed to generate image prompt for {title}")
            return False
        # 生成的图片提示词   
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