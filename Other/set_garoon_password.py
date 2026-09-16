"""Garoon のログイン名とパスワードを Windows 資格情報マネージャーに保存する。

移行後の同期(ScheduleSync.py)は Garoon の REST API を使い、認証に
`X-Cybozu-Authorization: base64("ログイン名:パスワード")` ヘッダを必要とする。
パスワードをリポジトリやコマンド履歴に残さないよう、keyring 経由で
Windows 資格情報マネージャーに預けておく。

    pixi run python Other/set_garoon_password.py

パスワードを変更したときは再実行するだけでよい。
"""

import getpass

import keyring

from Garoon.Client import KEYRING_SERVICE

#ログイン名そのものは秘密ではないが、実行時に引けると便利なので
#固定キー '__login__' で一緒に保存しておく
LOGIN_KEY = '__login__'


def main():
    default_login = keyring.get_password(KEYRING_SERVICE, LOGIN_KEY) or ''
    prompt = f'Garoon のログイン名 [{default_login}]: ' if default_login else 'Garoon のログイン名: '
    login = input(prompt).strip() or default_login
    if not login:
        raise SystemExit('ログイン名が入力されなかったため中止しました。')

    password = getpass.getpass(f'Garoon ({login}) のパスワード: ')
    if not password:
        raise SystemExit('パスワードが入力されなかったため中止しました。')

    keyring.set_password(KEYRING_SERVICE, LOGIN_KEY, login)
    keyring.set_password(KEYRING_SERVICE, login, password)

    ok = keyring.get_password(KEYRING_SERVICE, login) == password
    print(f'保存しました: service={KEYRING_SERVICE!r} login={login!r}')
    print('確認:', 'OK' if ok else 'NG')


if __name__ == '__main__':
    main()
