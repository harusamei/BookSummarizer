# 解析LLM输出的结果，提取最终信息
# taskname须与prompt.txt中的taskname一致
# 解析方法遵循prompt中output格式要求
# NOTE： prompt.txt 中taskname, output格式如有修改，需同步修改此文件
###########################################
import re
import copy
import json
class AnsExtractor:

    def __init__(self):
        self.result = {'status': 'succ', 'msg': ''}
        # 默认 parse_json
        self.tasks = {
            'nl2sql': self.parse_nl2sql,
            'sql_revise': self.parse_sql_statement,
            'sql_details': self.parse_sql_statement,
            'pattern': self.parse_llm_output,
            'default': self.parse_json
        }

    def output_extr(self, taskname, llm_answer):
        # 存在解析方法
        callFunc = self.tasks.get(taskname,self.parse_json)
        return callFunc(llm_answer)

    # 解析从LLM获得的分组信息
    def parse_grouping(self, llm_answer) -> dict:

        result = copy.copy(self.result)
        result['msg'] = None
        groups = {}
        data = llm_answer.split('\n')
        data =[d.strip() for d in data if d.strip()]
        # 流水线式抽取
        pattern = r"^Group\s+(\d+):\s+(.+)$"
        tArea = 'empty'
        name,desc, tables = '', '', ''
        for row in data:
            matched = re.match(pattern, row)
            if matched:
                if name!='':
                    groups[name] = {'group_desc': desc, 'tables': tables}
                group_id = matched.group(1)
                name = matched.group(2)
                desc,tables ='',''
                tArea = 'empty'
                continue
            if '--------' in row:
                if name != '':
                    groups[name] = {'group_desc': desc, 'tables': tables}
                name, desc, tables = '', '', ''
                tArea = 'empty'
                continue
            if 'group description' in row.lower():
                tArea = 'desc'
                desc = row.split(':')[-1].strip()   
                continue
            if 'included tables' in row.lower():
                tArea = 'tables'
                continue
            if tArea == 'desc':
                desc = desc+' '+row
            if tArea == 'tables':
                tables = tables+' '+row

        if name != '':
           groups[name] = {'group_desc': desc, 'tables': tables}

        if not groups:
            result['status'] = 'failed'
            return result
    
        for name, g_info in groups.items():
            tb_list = g_info['tables'].replace(' ',',').split(',')
            tb_list = [t.strip() for t in tb_list if re.match(r'^[^0-9\W]+', t.strip())]  # 只保留字母、数字和下划线
            groups[name]['tables'] = tb_list

        result['msg'] = groups
        return result
    
    # 解析从LLM获得的SQL提取信息
    def parse_json(self, llm_answer) -> dict:
        result = copy.copy(self.result)

        llm_answer = re.sub(r'[\x00-\x1F]+', ' ', llm_answer)  # 替换控制字符为单个空格
        llm_answer = llm_answer.strip()  # 去除首尾空格

        tlist = llm_answer.split('```json', 1)
        if len(tlist) >1:
            asw = tlist[1]
        else:
            asw = llm_answer
        # 只提取第一个json
        asw = asw.split('```', 1)[0]
        asw = asw.strip()
        asw = re.sub(r',\s*([\]}])', r'\1', asw)    # trailing comma
        
        try:
            # 将 JSON 字符串转换为字典
            asw = asw.replace('\"', '"')
            data = json.loads(asw)
            result['status'] = 'succ'
            result['msg'] = data
        except json.JSONDecodeError as e:
            print(f'Json decode error: {e}\n------------\n')
            result['status'] = 'failed'
            result['msg'] = llm_answer
            print(llm_answer)
        return result

    def parse_sql_statement(self, output) -> dict:

        result = copy.copy(self.result)

        patn = "```sql\n(.*?)\n```"
        matches = re.findall(patn, output, re.DOTALL | re.IGNORECASE)
        if matches:
            result['msg'] = matches[0]
        elif 'select' in output.lower():
            result['msg'] = output
        else:
            result['status'] = 'failed'
            result['msg'] = 'can not match pattern'
        
        return result
    
    def parse_expansion(self, llm_answer) -> dict:
        
        result = copy.copy(self.result)
        
        data = self.parse_table(llm_answer)
        new_terms = {}
        for row in data[1:]:
            if 'Term Expansions' in ' '.join(row):
                continue
            tList = list(set(row[1].split(',')))
            tList = [t.strip() for t in tList]
            new_terms[row[0]] = tList
        result['msg'] = new_terms
        return result
   
    def parse_desc(self, output) -> dict:
        result = copy.copy(self.result)
        tDict = {}
        pat1 = r"table:\s*(\S+)\s*\n"
        pat2 = r"table description:\s*(.+)\n"

        errFlag = False
        # 使用 re.IGNORECASE 标志进行忽略大小写的匹配
        match1 = re.search(pat1, output, re.IGNORECASE)
        match2 = re.search(pat2, output, re.IGNORECASE)
        if match1:
            tDict['table'] = match1.group(1)
        else:
            errFlag = True
        if match2:
            tDict['table_desc'] = match2.group(1)
        else:
            errFlag = True
        
        pat3 = r"\|\s*column_name\s*\|\s*description\s*\|"   
        match3 = re.search(pat3, output, re.IGNORECASE)
        if match3:
            pos = match3.start()
            colum_info = output[pos:]
            data = self.parse_table(colum_info)
            tDict['column_info'] = data
            result['msg'] = tDict
        else:
            errFlag = True
        
        if errFlag:
            print("error: no column_info found in result")
            result['status'] = 'failed'
            result['msg'] = "error: NOCOLUMN"
        
        return result
                
    # Extract the SQL code from the LLM result
    # 提取SQL代码, 提取sql 全部小写
    def parse_nl2sql(self, output: str) -> dict:
       
        result = copy.copy(self.result)
        
        if output.lower().startswith("```sql"):
            code_pa = "```sql\n(.*?)\n```"  # 标准code输出
        elif 'select' in output.lower():
            output = re.sub('\n|\t', ' ', output)
            output = re.sub(' +', ' ', output)
            code_pa = "(select.*?from[^;]+;)"  # 不一定有where
        else:
            #print("ERR: no sql found in result")
            result['status'] = 'failed'
            result['msg'] = "error: NO SQL"
            return result
        matches = re.findall(code_pa, output, re.DOTALL | re.IGNORECASE)
        if len(matches) == 0:
            #print("ERR: no sql found in result")
            result['status'] = 'failed'
            result['msg'] = "error: NO SQL"
        else:
            result['msg']=matches[0]
        
        return result
    # 通用模式匹配
    def parse_llm_output(self,output):
        # Define regular expressions to extract relevant information
        pattern1 = r"Pattern 1: (.+)"
        pattern2 = r"Pattern 2: (.+)"
        # Add more patterns as needed

        # Extract information using regular expressions
        match1 = re.search(pattern1, output)
        match2 = re.search(pattern2, output)
        # Add more matches as needed

        # Process the extracted information
        if match1:
            pattern1_result = match1.group(1)
            # Process pattern 1 result

        if match2:
            pattern2_result = match2.group(1)
            # Process pattern 2 result

        # Return the processed information
        return pattern1_result, pattern2_result
    
    #解析ascii表格为matric
    """ 
    | Keyword    | Label        |
    |------------|--------------|
    | apple      | Brand        |
    | mouse      | Product_name |
    | innovation | Business     | """
    # [['Keyword', 'Label'], ['apple', 'Brand'], ['mouse', 'Product_name'], ['innovation', 'Business']]
    @staticmethod
    def parse_table(table):
        # 去掉表格的边框和分隔线
        lines = table.strip().split('\n')
        lines = [line for line in lines if not re.match(r'^\|.*[-]{3,}', line)]
        
        # 解析每一行
        data = []
        for line in lines:
            # 去掉行首和行尾的竖线，并按竖线分割
            row = [cell.strip() for cell in line.strip('|').split('|')]
            if len(row)>1: 
                data.append(row)
        
        return data
    
if __name__ == "__main__":
    ans_extr = AnsExtractor()
    llm_output = """
```json
{
  "shots": [
    {
      "shot_number": 1,
      "shot_title": "The Threshold of Knowledge",
      "scene_description": "An ancient, weathered book lies half-open on a wooden desk. The title 'Faust' glows faintly on the page, as if etched in light. The background is a dimly lit study, with shadows stretching across the room. A single candle flickers, casting warm light onto the book while the edges of the frame remain steeped in cold, bluish darkness.",
      "composition": "The camera is positioned at a low, slightly tilted angle, focusing on the book in the foreground. The book is centered, with the candle placed slightly off to the right, creating a diagonal line of light and shadow. The background is blurred, emphasizing the book as the focal point.",
      "color_palette": "Warm golden tones from the candlelight contrast with deep, cold blues and grays in the shadows. The glowing title on the book is a luminous gold, symbolizing enlightenment amidst darkness.",
      "symbolic_elements": "The book represents forbidden knowledge and the eternal quest for understanding. The glowing title symbolizes the allure of wisdom, while the interplay of light and shadow reflects the internal conflict between aspiration and temptation. The candle serves as a fragile beacon of hope and clarity in an otherwise dark and mysterious setting."
    }
  ]
}
```
                """
    result1 = ans_extr.output_extr('default',llm_output)
    print(result1)
