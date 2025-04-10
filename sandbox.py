import sys
import os
import asyncio
import json
import pandas as pd
from LLM.prompt_loader1 import Prompt_generator
from LLM.llm_agent import LLMAgent
from LLM.ans_extractor import AnsExtractor

class BookSummary:

    def __init__(self):

        self.prompter = Prompt_generator()
        self.ans_extr = AnsExtractor()
        self.llm = LLMAgent()
        self.lang = 'Chinese'

    async def gen_bookInfo(self, title, author):
        tmpl = self.prompter.tasks['key_scenes']
        query = tmpl.format(title=title, author=author, language=self.lang)
        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('key_scenes', asw)
        if result['status'] == 'failed':
            print(f"Failed to generate brief intro for {title}")
            return None
        result = result['msg']

        self.write_to_json(f'{title}.json', result)
    
    async def gen_summary(self, json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            abook = json.load(f)
        title = abook['title']
        jsonstr = json.dumps(abook, ensure_ascii=False, indent=4)
        tmpl = self.prompter.tasks['b_video_script_2']
        query = tmpl.format(book_info=jsonstr, language=self.lang)
        asw = await self.llm.ask_llm(query, '')
        self.write_to_txt(f'{title}_bv.md', asw)

    @staticmethod
    def write_to_json(file_path, abook):
        with open(file_path, 'w',encoding='utf-8') as f:
            jsonStr = json.dumps(abook, ensure_ascii=False, indent=4)
            f.write(jsonStr)

    @staticmethod
    def write_to_txt(file_path, txt):
        with open(file_path, 'w',encoding='utf-8') as f:
            f.write(txt)

if __name__ == '__main__':

    bs = BookSummary()
    title = "荷马史诗"
    author = "荷马"
    #asyncio.run(bs.gen_bookInfo(title, author))
    asyncio.run(bs.gen_summary('bookInfo.json'))
    print("done")
