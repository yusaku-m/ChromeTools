"""OneDrive(職場)のパス解決。

../GRADING の packages/paths.py と同じ方式: OneDrive フォルダの場所は PC ごとに違う
(開発PCはホーム直下、本番PCは D:\\ 等)ので候補ルートを順に試し、実際に使う
Work/講義 まであるものを優先する。同じ名前の OneDrive フォルダが旧ドライブに抜け殻として
残っている PC があり、最上位フォルダの有無だけで選ぶと中身の無い方を拾うため。
OneDrive クライアントが設定する環境変数 OneDriveCommercial があれば最優先で使う。
"""

import os

ONEDRIVE_NAME = "OneDrive - 独立行政法人 国立高等専門学校機構"
ONEDRIVE_ROOTS = [
    r"C:\Users\Yusaku",
    "E:",
    "D:",
    r"C:\Users\jagai",
    r"C:\Users\Yusaku MAEDA",
]


def _candidates():
    cands = []
    env = os.environ.get('OneDriveCommercial')
    if env:
        cands.append(os.path.normpath(env))
    for root in ONEDRIVE_ROOTS:
        #裸のドライブ文字("D:")を os.path.join に渡すとドライブ相対パスになるので区切りを補う
        cands.append(os.path.join(root + os.sep if root.endswith(':') else root, ONEDRIVE_NAME))
    return cands


def onedrive_root():
    """OneDrive フォルダ({ルート}/OneDrive - 独立行政法人 …)を返す。無ければ例外。"""
    cands = _candidates()
    for c in cands:
        if os.path.isdir(os.path.join(c, 'Work', '講義')):
            return c
    for c in cands:
        if os.path.isdir(c):
            return c
    raise FileNotFoundError("OneDrive のフォルダが見つかりません。paths.ONEDRIVE_ROOTS を確認してください。")


def onedrive_dir(*parts):
    """{OneDrive}/parts… を返す。"""
    return os.path.join(onedrive_root(), *parts)
