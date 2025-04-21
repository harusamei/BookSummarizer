# flake8: noqa
# 生成视频脚本中的静态图
import sys,os
import pandas as pd
from LLM.prompt_loader1 import Prompt_generator
from LLM.llm_agent import LLMAgent
from LLM.ans_extractor import AnsExtractor
sys.path.insert(0, os.getcwd().lower())
from LLM.dall_image import txt2image, save_image_with_prompt


class BookImage:

   def __init__(self):
      self.prompter = Prompt_generator()
      self.ans_extr = AnsExtractor()
      self.llm = LLMAgent()

   async def gen_image_desc(self, xls_file):
      books = pd.read_excel(xls_file, sheet_name=0)
      file_dir = os.path.dirname(os.path.abspath(xls_file))
      tmpl = self.prompter.tasks['image_description']
      failed_books = []
      for _, row in books.iterrows():
         title = row['title']
         print(f'title: {title}')
         with open(os.path.join(file_dir, f'{title}_bv.md'), 'r',encoding='utf-8') as f:
            vscript = f.read()
         if len(vscript) == 0:
            failed_books.append(title)
            continue
         query = tmpl.format(vscript=vscript)
         asw = await self.llm.ask_llm(query, '')
         result = self.ans_extr.output_extr('image_description', asw)
         if result['status'] == 'failed':
            print(f"Failed to generate image description for {title}")
            failed_books.append(title)
            continue
         self.write_to_json(os.path.join(file_dir, f'{title}_img.json'), result['msg'])

      print(f"Failed books: {failed_books}")
      return failed_books