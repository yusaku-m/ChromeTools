# EdgeTools
ブラウザ関連諸々の自動化用

# ./Edge/Browser.py
## Browserクラス
基本クラス。Edgeの起動や設定，終了を扱う
### __init__ 
必要なドライバをダウンロードして，ブラウザを起動する。引数 userdata_path は edge://version/ の Profile path を使用すると該当ユーザーで保存しているパスワードが有効に
    
### close
ブラウザを閉じる

# ./Edge/Kaikei.py
## Kaikeiクラス
Browserの子クラス。見える会計への明細入力用
### __init__
保存済みパスでログイン

### input_order
指定した注文リストを入力





