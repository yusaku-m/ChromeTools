import os
from Chrome.Browser import Browser
from Chrome.Kaikei import Kaikei
from Chrome.Kaikei import Order

user_data_path = "C:/Users/Yusaku/AppData/Local/Google/Chrome/User Data/"
browser = Kaikei(user_data_path)

import pandas as pd
dir = 'C:/Users/Yusaku/独立行政法人 国立高等専門学校機構/前田研究室 - General/研究室資料/物品購入'
df = pd.read_csv(f'{dir}/ItemList20230404.csv', header=0, encoding = 'shift_jis')
print(df)
for index, row in df.iterrows():
    print(row)
    item        = f'{row["品名"]}'#_{row["型番"]}'
    quantity    = row["数量"]
    unit_price  = row["単価（税込）"]
    place       = row["納入場所"]
    organization= row["執行組織"]
    budget      = row["予算"]
    #購入依頼データを作成
    order = Order(item, quantity, unit_price, place, organization, budget)
    #購入依頼を入力
    browser.input_order(order)

    
browser.close(1)