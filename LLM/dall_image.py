# flake8: noqa
# 文生图模型
import http.client
import json
import requests
import asyncio
from PIL import Image, PngImagePlugin
import os
import sys
from io import BytesIO
sys.path.insert(0, os.getcwd())
from settings import z_config

agentName = 'CHATANYWHERE'
key = z_config['LLM',f'{agentName}_KEY']
async def txt2image(prompt):
   
   payLoad = makePayload(prompt)
   imgUrl = await askDall(payLoad)
   return imgUrl

def makePayload(prompt):
   # 生成图像
   payload = json.dumps({
      "prompt": prompt,
      "n": 1,
      "model": "dall-e-3",
      "size": "512x512"
   })
   return payload

async def askDall(payload):
   # 生成图像
   conn = http.client.HTTPSConnection("api.chatanywhere.tech")
   headers = {
      'Authorization': f'Bearer {key}',
      'Content-Type': 'application/json'
   }
   conn.request("POST", "/v1/images/generations", payload, headers)
   res = conn.getresponse()
   data = res.read()
   print(data.decode("utf-8"))
   response_json = json.loads(data.decode("utf-8"))
   image_url = response_json['data'][0]['url']

   print(f"生成的图像URL: {image_url}")
   return image_url

async def download_image(image_url, output_path):
   # 下载图像
   img_data = requests.get(image_url).content
   # 保存到本地
   img = Image.open(BytesIO(img_data.content))
   img.save(output_path, "PNG")

# 保存元信息只能使用png格式
async def save_image_with_prompt(image_url, prompt, output_path='image.png'):
   # 下载图像
   response = requests.get(image_url)
   img = Image.open(BytesIO(response.content))

   # 添加描述到元数据
   metadata = PngImagePlugin.PngInfo()
   metadata.add_text("Description", prompt)

   # 保存图像并附加元数据
   img.save(output_path, "PNG", pnginfo=metadata)

def view_image_metadata(image_file):
    """
    查看图像的元数据。
    """
    img = Image.open(image_file)
    metadata = img.info  # 获取图像的元数据

    if metadata:
        print("图像元数据:")
        for key, value in metadata.items():
            print(f"{key}: {value}")
    else:
        print("该图像没有元数据。")


if __name__ == '__main__':
   context = "有一个参考图片，图的内容是 A close-up of the book '《生命3.0》' placed on a wooden table. The book is illuminated by a soft, warm spotlight, creating a cozy and inviting atmosphere. The background is slightly blurred, showing a hint of a modern study room with bookshelves and a glowing desk lamp. The book cover features a sleek design with a futuristic font and a faint image of a glowing DNA helix intertwined with a digital circuit pattern. The lighting highlights the book as the focal point, with a subtle golden glow around its edges."  
   prompt = "请根据参考图片的信息，生成一张新图片，内容是 A close-up of the book '《生命3.0》' being gently closed by a hand. The scene is warmly lit, with a golden glow from a nearby lamp. The background shows a cozy study setup with a steaming cup of tea, a notebook, and a pair of glasses resting on the table. The atmosphere is calm and reflective, symbolizing the end of the discussion and an invitation for personal contemplation."
   img_file = 'image.png'
   wk_dir = os.getcwd()
   img_path = os.path.join(wk_dir, img_file)
   img_url = asyncio.run(txt2image(f'{context}\n{prompt}'))
   asyncio.run(save_image_with_prompt(img_url,prompt,output_path='image1.png'))
   view_image_metadata('image1.png')
   print('Image downloaded successfully!')
