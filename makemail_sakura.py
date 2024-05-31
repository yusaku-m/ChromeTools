import Chrome

print("test")

excelpath = r"C:\Users\Yusaku\OneDrive - 独立行政法人 国立高等専門学校機構\Work\講義\そのた科目\さくら連絡網.xlsx"
sheetname = r"出力"

message = Chrome.Message()
message.get_data_from_excel(excelpath, sheetname)

user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
sakura = Chrome.Sakura(user_data_path)

sakura.make_mail(message)

input()