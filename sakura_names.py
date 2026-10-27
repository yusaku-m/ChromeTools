"""さくら連絡網での表示名の辞書(OneDrive。Excel・KOSEN WEB の氏名と表示名が違う学生用)。

SHR.xlsx や KOSEN WEB の氏名が、さくら連絡網の受信者一覧の表示名と一致しない学生がいる
(異体字・登録時の表記ゆれ等)。照合できなかったときに表示名を打ち込んでもらい、
Work/講義/そのた科目/sakura_name_alias.csv(列: 氏名, さくら表示名)に追記して次回から使う。

**中身は個人情報。Claude はこのファイルを読まないこと**(ユーザーの指示)。
"""

import csv
import os

from Chrome.Sakura import normalize_name
from paths import onedrive_dir

ALIAS_FILE = ('Work', '講義', 'そのた科目', 'sakura_name_alias.csv')
HEADER = ['氏名', 'さくら表示名']


def alias_path():
    return onedrive_dir(*ALIAS_FILE)


def load_aliases():
    """{正規化した氏名: さくら表示名}。後の行ほど優先。"""
    aliases = {}
    try:
        with open(alias_path(), encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('氏名') and row.get('さくら表示名'):
                    aliases[normalize_name(row['氏名'])] = row['さくら表示名']
    except FileNotFoundError:
        pass
    return aliases


def to_sakura_names(names, aliases=None):
    """氏名のリストを、辞書に登録があればさくら連絡網の表示名に置き換えて返す。"""
    aliases = load_aliases() if aliases is None else aliases
    return [aliases.get(normalize_name(n), n) for n in names]


def add_alias(name, display_name):
    path = alias_path()
    while True:
        try:
            new = not os.path.exists(path)
            #Excel で文字化けしないよう BOM 付き UTF-8(先頭に書くときだけ BOM が付く)
            with open(path, 'a', encoding='utf-8-sig' if new else 'utf-8', newline='') as f:
                writer = csv.writer(f)
                if new:
                    writer.writerow(HEADER)
                writer.writerow([name, display_name])
            return
        except PermissionError:
            input(f"  表示名の辞書に書き込めません(Excel で開いていれば閉じてください): {path}\n  Enter で再試行: ")


def ask_aliases(students):
    """照合できなかった学生 [(出席番号, 氏名), ...] について、さくら連絡網での表示名を打ち込んでもらい
    辞書に登録する。1件でも登録したら True。"""
    added = False
    for number, name in students:
        #手動で対応するために氏名が要るので、一致しなかった学生に限り表示する(ユーザーの指示)
        print(f"  さくら連絡網で宛先が見つかりませんでした(出席番号 {number} {name})。")
        display = input("  さくら連絡網での表示名を入力してください(登録して次回から使います。空 Enter で登録しない): ").strip()
        if display:
            add_alias(name, display)
            added = True
    return added
