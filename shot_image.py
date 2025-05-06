# flake8: noqa
# 生成视频脚本中的静态图
import sys,os
import pandas as pd
import asyncio
import re
import time
import json
import random
sys.path.insert(0, os.getcwd().lower())
from LLM.dall_image import txt2image, save_image_with_prompt

class ShotImage:

   def __init__(self):
      self.exts = {
         'visualDesc': '_desc.json'     # 图像，视频描述
        }
      self.genMode = "random"             # 生成模式，all所有，random 随机5个，completion

   async def gen_batch(self, xls_file):
      books = pd.read_excel(xls_file, sheet_name=0)
      books.columns = books.columns.str.strip()  # 去除列名中的多余空格
      books.fillna(inplace=True, value='')
      book_dir = os.path.dirname(os.path.abspath(xls_file))
      
      for _, row in books.iterrows():
         title = row['title']
         if title.startswith('《'):
               title = title[1:-1]
         print(f'title: {title}')
         bname_dir = os.path.join(book_dir, title)
         if not os.path.exists(bname_dir):
            print(f"Directory {bname_dir} does not exist.")
            continue
         ext = self.exts['visualDesc']
         filePath = os.path.join(f'{bname_dir}/data', f'{title}{ext}')
         if not os.path.exists(filePath):
            print(f"File {filePath} does not exist.")
            continue
         with open(filePath, 'r',encoding='utf-8') as f:
            shots = json.load(f)
         shots = shots['shots']
         imgPath = os.path.join(bname_dir, 'images')
         if not os.path.exists(imgPath):
            os.makedirs(imgPath)
         start_time = time.time()
         shots = self.get_shots(shots, imgPath)
         for i, shot in enumerate(shots):
            if 'img_prompt' not in shot:
               print(f"img_prompt not found in shot {i}")
               continue
            if i >= 5:
               break
            img_desc = shot['img_prompt']['prompt_en']
            section = shot['segment_title']
            print(f'{section}, finished: {i+1}/{len(shots)}')
            outFile = f"shot_{shot['shot_number']}"
            fileName = os.path.join(imgPath, outFile)
            flag = await self.gen_image(img_desc, fileName)
            if flag is False:
               print(f"Failed to generate image for shot_{shot['shot_number']}")
               tDict = {'shot_number': shot['shot_number'], 'image_description': img_desc}
         print(f"Time taken for {title}: {time.time() - start_time:.2f} seconds")
         break
      
      return
   
   def get_shots(self, shots, imgPath):
      if self.genMode == 'all':
         return shots
      elif self.genMode == 'random':
         random_shots = random.sample(shots, min(5, len(shots)))  # 确保 shots 少于 5 个时不会报错
         return random_shots
      # 补齐没有图片的镜头
      keep_shots = []
      for i, shot in enumerate(shots):
         filePath = os.path.join(imgPath, f"shot_{shot['shot_number']}.png")
         if os.path.exists(filePath):
            continue
         keep_shots.append(shot)
      return keep_shots


   # outFile只有文件名，没有扩展名
   async def gen_image(self, img_desc, baseFile):
      img_url =await txt2image(img_desc)
      if img_url is None:
         print(f"Failed to generate image for {img_desc}")
         return False

      ext = '.png'
      outFile = baseFile+ext
      count = 1
      while os.path.exists(outFile) and count < 10:
         print(f"Image {outFile} already exists.")
         outFile = f'{baseFile}({count}){ext}'
         count += 1
      
      # 保存元信息只能使用PNG格式
      return await save_image_with_prompt(img_url, img_desc, outFile)
      
if __name__ == '__main__':

    out_path ='books'
    wk_dir = os.getcwd()
    directory = os.path.join(wk_dir, out_path)
    xls_file = os.path.join(directory, 'booklist.xlsx')
    print(f"xls_file: {xls_file}")
    sv = ShotImage()
    asyncio.run(sv.gen_batch(xls_file))  