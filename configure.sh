# /usr/bin/env bash

# daemon用のサービスファイルの内容を環境に合わせて設定します
dir=$(cd $(dirname $0); pwd)

python3 -m pip install Configparser
python3 ${dir}/service/service.py --dir ${dir}
sudo ln -is ${dir}/service/chappie.service /etc/systemd/system/chappie.service
sudo systemctl daemon-reload

exit 0

