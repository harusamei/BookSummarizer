import asyncio
import json
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
        tmpl = self.prompter.tasks['b_video_script']
        query = tmpl.format(book_info=jsonstr)
        asw = await self.llm.ask_llm(query, '')
        self.write_to_txt(f'{title}_bv.md', asw)

    async def rewrite(self, title):
        txt_file = f'books/{title}_std.md'
        json_file = f'books/{title}.json'
        with open(txt_file, 'r', encoding='utf-8') as f:
            intro_txt = f.read()
        with open(json_file, 'r', encoding='utf-8') as f:
            abook = json.load(f)
        bookInfo = json.dumps(abook, ensure_ascii=False, indent=4)

        tmpl = self.prompter.tasks['video_structure']
        query = tmpl.format(book_info=bookInfo, std_txt=intro_txt)
        with open('temp_query.txt', 'w', encoding='utf-8') as f:
            f.write(query)
        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('video_structure', asw)
        if result['status'] == 'failed':
            print(f"Failed to rewrite introduction for {title}")
            return None
        result = result['msg']
        self.write_to_json(f'books/{title}_vid.json', result)

    async def image_desc(self, title):
        json_file = f'books/{title}_vid.json'
        with open(json_file, 'r', encoding='utf-8') as f:
            vid = json.load(f)
        vid_stru = json.dumps(vid, ensure_ascii=False, indent=4)

        tmpl = self.prompter.tasks['visual_desc']
        query = tmpl.format(vid_stru=vid_stru)
        with open('temp_query.txt', 'w', encoding='utf-8') as f:
            f.write(query)

        asw = await self.llm.ask_llm(query, '')
        result = self.ans_extr.output_extr('visual_desc', asw)
        if result['status'] == 'failed':
            print(f"Failed to generate image description for {title}")
            return None
        self.write_to_json(f'books/{title}_img.json', result['msg'])

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
    # title = "何以笙箫默"
    # author = "顾漫"
    #asyncio.run(bs.gen_bookInfo(title, author))
    #asyncio.run(bs.gen_summary('bookInfo.json'))
    #asyncio.run(bs.rewrite('浮士德'))
    asyncio.run(bs.image_desc('浮士德'))
    print("done")
