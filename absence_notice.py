"""サイボウズに欠席連絡がある学生(出席番号)を、さくら連絡網の宛先から除外するための引数。

SHR 欠席者連絡・授業欠課者連絡の両方で `-x 3,15,22` のように出席番号を渡す。
Garoon の「学生欠席等連絡」カレンダーから自動で引く(docs/backlog_garoon.md の4)までの手動版。
"""

import argparse
import re


def number_key(number):
    """出席番号の表記ゆれ('03' / '3' / '3.0' / 全角)を吸収した比較用の値。数字でなければ空白を除いた文字列。"""
    text = str(number).strip()
    try:
        return int(float(text))
    except ValueError:
        return text


def parse_numbers(text):
    """'3,15 22' → {3, 15, 22}。区切りはカンマ・読点・空白。"""
    parts = [p for p in re.split(r'[,，、\s]+', text) if p]
    keys = {number_key(p) for p in parts}
    if not all(isinstance(k, int) for k in keys):
        raise argparse.ArgumentTypeError(f"出席番号は数字をカンマ区切りで指定してください: {text}")
    return keys


def add_argument(parser):
    parser.add_argument('-x', '--exclude', type=parse_numbers, action='append', default=[],
                        metavar='3,15,22',
                        help='サイボウズで欠席連絡がある学生の出席番号(カンマ区切り)。宛先から除外する')


def excluded(args):
    return set().union(*args.exclude)


def split(students, exclude, number=lambda s: s[0]):
    """students を (除外しないもの, 除外したもの) に分け、除外の結果を出席番号だけで表示する。"""
    kept = [s for s in students if number_key(number(s)) not in exclude]
    removed = [s for s in students if number_key(number(s)) in exclude]
    if exclude:
        print(f"サイボウズの欠席連絡で除外: {len(removed)} 名"
              + (f"(出席番号 {', '.join(str(number(s)) for s in removed)})" if removed else ''))
        unused = sorted(exclude - {number_key(number(s)) for s in students})
        if unused:
            print(f"  指定した出席番号のうち {', '.join(map(str, unused))} は対象者にいません(入力ミスでなければ問題ありません)。")
    return kept, removed
