# 制作书籍的简介和视频脚本
####################################################
import sys
import os
import asyncio
import json
import pandas as pd
from LLM.prompt_loader1 import Prompt_generator
from LLM.llm_agent import LLMAgent
from LLM.ans_extractor import AnsExtractor
from processor import DProcessor
sys.path.insert(0, os.getcwd().lower())


class BookSummary:
    def __init__(self, language='Chinese'):

        self.prompter = Prompt_generator()
        self.ans_extr = AnsExtractor()
        self.llm = LLMAgent()
        self.dp = DProcessor()      # data processor
        self.lang = language
        # 文件使用的扩展名
        self.exts = {
            'bookInfo': '.json',
            'introduction': '_std.md',  # 文字版导言
            'videoScript': '_bv.md',    # B站风视频脚本
            'visualDesc': '_desc.json',    # 图像，视频描述
            'official': '_intro.txt',      # 官方或书籍序言
            'videoStructure': '_vid.json'  # 视频结构
        }

    async def gen_batch(self, xls_file):
        books = pd.read_excel(xls_file, sheet_name=0)
        books.columns = books.columns.str.strip()  # 去除列名中的多余空格
        books.fillna(inplace=True,value='')
        book_dir = os.path.dirname(os.path.abspath(xls_file))
        
        for _, row in books.iterrows():
            hasWritten, hasIntroduction = False, False
            title = row['title']
            if title.startswith('《'):
                title = title[1:-1]
            author = row['author']
            hasIntroduction = row['hasIntroduction']
            hasWritten = row['hasWritten']
            if hasWritten.lower() == 'y':
                hasWritten = True
            if hasIntroduction.lower() == 'y':
                hasIntroduction = True
           
            print(f'author: {author}, title: {title}')
            await self.gen_bookInfo(title, author, book_dir)
            print('part 1: generate book summarization')
            # 有人工写的导读
            if hasWritten is True:
                print(f"Book {title} already has a human-written.")
            elif hasIntroduction is True:   # 书籍序言或专业导读
                print(f"Book {title} already has an official introduction .")
                await self.rewrite_intro(title, author, book_dir)
            else:
                await self.gen_introduction(title, author, book_dir)
        
            print('part 2: generate visual content')
            await self.gen_videoStructure(title, book_dir)
            await self.gen_visualDesc(title, book_dir)
            
            print('part 3: generate video script')
            await self.gen_videoScript(title, author, book_dir)
    
    # 输出json 存放在book_dir 目录下
    async def gen_bookInfo(self, title, author, book_dir):

        tmpls = {}
        tasks1 = ['brief_intro', 'key_scenes']
        print(tasks1)

        for key in tasks1:
            tmpls[key] = self.prompter.tasks[key]

        abook = {}
        for key in tasks1:
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
        ext = self.exts['bookInfo']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            abook = json.load(f)
        if len(abook.keys()) == 0:
            abook['author'] = author
            abook['title'] = title
        jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
        query = tmpl.format(book_info=jsonStr)
        asw = await self.llm.ask_llm(query, '')
        ext = self.exts['introduction']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)

        return
    
    async def rewrite_intro(self, title, author, book_dir):
        print(f"rewrite intro for {title}")
        tmpl = self.prompter.tasks['intro_rewrite']
        ext = self.exts['bookInfo']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            abook = json.load(f)
        if len(abook.keys()) == 0:
            abook = {}
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        ext = self.exts['official']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            oguide = f.read()
        if len(oguide) == 0:
            print(f"Failed to read {title}{ext} in rewrite_intro.")
            return False
        query = tmpl.format(book_info=bookInfo, intro_txt=oguide)
        # with open('temp_query.txt', 'w', encoding='utf-8') as f:
        #     f.write(query)

        asw = await self.llm.ask_llm(query, '')
        ext = self.exts['introduction']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)

        return True
    
    # TODO 0418
    async def gen_videoScript(self, title, author, book_dir):
        
        tmpl = self.prompter.tasks['b_video_script']
        ext = self.exts['videoStructure']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        vid_stru = json.dumps(vid, ensure_ascii=False, indent=4)
        ext = self.exts['introduction']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        query = tmpl.format(vid_stru=vid_stru, std_txt=intro_txt)
        asw = await self.llm.ask_llm(query, '')

        ext = self.exts['videoScript']
        self.dp.save_txt(os.path.join(book_dir, f'{title}{ext}'), asw)
        
    
    # 基于文字版intro+bookinfo 生成视频结构
    async def gen_videoStructure(self, title, book_dir):
        print(f"gen_videoStructure for {title}")

        tmpl = self.prompter.tasks['video_structure']
        ext = self.exts['bookInfo']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            abook = json.load(f)
        if len(abook.keys()) == 0:
            abook = {}
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        ext = self.exts['introduction']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        if len(intro_txt) == 0:
            print('failed to read introduction')
            return False
        query = tmpl.format(std_txt=intro_txt, book_info=bookInfo)
        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('video_structure', asw)
        if result['status'] == 'failed':
            print(f"Failed to generate video structure for {title}")
            return False
        result = result['msg']
        ext = self.exts['videoStructure']
        self.dp.save_json(os.path.join(book_dir, f'{title}{ext}'), result)
        return True
    
    async def gen_visualDesc(self, title, book_dir):
        print(f"gen_visualDesc for {title}")

        tmpl = self.prompter.tasks['visual_desc']
        ext = self.exts['videoStructure']
        with open(os.path.join(book_dir, f'{title}{ext}'), 'r', encoding='utf-8') as f:
            vid = json.load(f)
        secs = vid['video_structure']
        allDesc = []
        for sec in secs:
            print(f"sec: {sec['section']}")
            vidInfo = json.dumps(sec, ensure_ascii=False, indent=4)
            query = tmpl.format(vid_stru=vidInfo)
            asw = await self.llm.ask_llm(query, '')
            result = self.ans_extr.output_extr('video_structure', asw)
            if result['status'] == 'failed':
                print(f"Failed to generate video structure for {title}")
                continue
            result = result['msg']
            allDesc.extend(result['shots'])
        for i, item in enumerate(allDesc):
            item['image_number'] = i+1
        ext = self.exts['visualDesc']
        self.dp.save_json(os.path.join(book_dir, f'{title}{ext}'), {'shots': allDesc })
        return True

if __name__ == '__main__':

    out_path ='books'
    wk_dir = os.getcwd()
    directory = os.path.join(wk_dir, out_path)
    xls_file = os.path.join(directory, 'booklist.xlsx')
    print(f"xls_file: {xls_file}")
    bs = BookSummary()
    asyncio.run(bs.gen_batch(xls_file))

    print("Done!")