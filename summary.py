import sys
import os
import asyncio
import json
import pandas as pd
from LLM.prompt_loader1 import Prompt_generator
from LLM.llm_agent import LLMAgent
from LLM.ans_extractor import AnsExtractor
sys.path.insert(0, os.getcwd().lower())


class BookSummary:
    def __init__(self):

        self.prompter = Prompt_generator()
        self.ans_extr = AnsExtractor()
        self.llm = LLMAgent()

    async def gen_bookInfo(self, xls_file):

        sheets = pd.read_excel(xls_file, sheet_name=None)
        books = sheets['Sheet1']
        
        tmpls = {}
        tasks1 = ['brief_intro', 'key_scenes']
        for key in tasks1:
            tmpls[key] = self.prompter.tasks[key]

        file_dir = os.path.dirname(os.path.abspath(xls_file))
        abook = {}
        failed_books = []
        for _, row in books.iterrows():
            abook.clear()
            title = row['title']
            author = row['author']
            print(f'author: {author}, title: {title}')
            for key in tasks1:
                print(f"key: {key}")
                query = tmpls[key].format(title=title, author=author, language='Chinese')
                asw = await self.llm.ask_llm(query, '')
                result = self.ans_extr.output_extr(key, asw)
                if result['status'] == 'failed':
                    print(f"Failed to generate {key} for {title}")
                    failed_books.append(title)
                    break
                result = result['msg']
                abook.update(result)

            self.write_to_json(os.path.join(file_dir, f'{title}.json'), abook)
            

        print(f"Failed books: {failed_books}")
        return failed_books

    async def gen_summary(self, xls_file):
        sheets = pd.read_excel(xls_file, sheet_name=None)
        books = sheets['Sheet1']
        file_dir = os.path.dirname(os.path.abspath(xls_file))
        abook = {}
        tmpls = {}
        tasks2 = ['book_introduction', 'b_video_script']
        for key in tasks2:
            tmpls[key] = self.prompter.tasks[key]
        failed_books = []
        for _, row in books.iterrows():
            title = row['title']
            author = row['author']
            print(f'author: {author}, title: {title}')
            with open(os.path.join(file_dir, f'{title}.json'), 'r',encoding='utf-8') as f:
                abook = json.load(f)
            if len(abook.keys()) == 0:
                abook['author'] = author
                abook['title'] = title
            else:
                continue
            
            jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
            ext = 'std'
            for key in tasks2:
                print(f"key: {key}")
                query = tmpls[key].format(book_info=jsonStr)
                asw = await self.llm.ask_llm(query, '')
                if key == 'b_video_script':
                    ext = 'rb'
                self.write_to_txt(os.path.join(file_dir, f'{title}_{ext}.md'), asw)
              
    @staticmethod
    def write_to_json(file_path, abook):
        with open(file_path, 'w', encoding='utf-8') as f:
            jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
            f.write(jsonStr)

    @staticmethod
    def write_to_txt(file_path, txt):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(txt)


if __name__ == '__main__':

    out_path='books'
    wk_dir = os.getcwd()
    directory = os.path.join(wk_dir,out_path)
    xls_file = os.path.join(directory, 'booklist.xlsx')
    print(f"xls_file: {xls_file}")
    bs = BookSummary()
    #asyncio.run(bs.gen_bookInfo(xls_file))
    asyncio.run(bs.gen_summary(xls_file))

    print("Done!")