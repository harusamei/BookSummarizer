# 数据预处理和保存
from docx import Document
import os
import json


class DProcessor:
    def __init__(self):
        pass

    def word_to_txt(self, aDocx_file):
        try:
            doc = Document(aDocx_file)
            return [paragraph.text for paragraph in doc.paragraphs]
        except Exception as e: 
            print(f'Error: {e}')
            return None

    @staticmethod
    def save_json(file_path, tJson):
        with open(file_path, 'w', encoding='utf-8') as f:
            jsonStr = json.dumps(tJson, ensure_ascii=False, indent=4)
            f.write(jsonStr)

    @staticmethod
    def save_txt(file_path, txt):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(txt)
       
    def process_docs(self, fileList):
        for file in fileList:
            file = file.lower()
            paras = self.word_to_txt(file)
            if paras is None:
                continue
            txtName = file.split('.doc')[0] + '.txt'
            print(f"txtName: {txtName}")
            with open(txtName, 'w', encoding='utf-8') as f:
                for para in paras:
                    f.write(para + '\n')

        print(f"Processed {len(fileList)} files.")

    def get_doc_list(self, directory, exts=['doc', 'docx']):
        file_list = []
        for root, _, files in os.walk(directory):
            for file in files:
                file_list.append(os.path.join(root, file))
        fileNames = []
        docList = []
        for file in file_list:
            fileName = os.path.basename(file)
           
            if fileName.lower().endswith(tuple(exts)):
                if fileName not in fileNames:
                    fileNames.append(fileName)
                    docList.append(file)
        return docList


if __name__ == '__main__':
    doc_path = 'rwbooks'
    wk_dir = os.getcwd()
    directory = os.path.join(wk_dir, doc_path)
    dp = DProcessor()
    fileList = dp.get_doc_list(directory)
    print(f"Total {len(fileList)} files.")
    print(fileList)

    dp.process_docs(fileList)
