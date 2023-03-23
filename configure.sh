# /usr/bin/env bash

# daemon用のサービスファイルの内容を環境に合わせて設定します
dir=$(cd $(dirname $0); pwd)

python3 -m pip install discord==2.2.*
python3 -m pip install python-dotenv==1.0.*
python3 -m pip install openai==0.27.*
python3 -m pip install PyYAML==6.0
python3 -m pip install dacite==1.6.*
python3 -m pip install Configparser
python3 ${dir}/service/service.py --dir ${dir}
sudo ln -is ${dir}/service/chappie.service /etc/systemd/system/chappie.service
sudo systemctl daemon-reload

exit 0

