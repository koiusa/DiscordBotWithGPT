import os
import getpass
import inspect
import argparse
import configparser

parser = argparse.ArgumentParser()
parser.add_argument('--dir')
args = parser.parse_args()

config = configparser.ConfigParser()
config.optionxform = str
config.read(f"{os.path.dirname(__file__)}/chappie.service")

config.set('Service','ExecStart', f"{args.dir}/src/main.py")
config.set('Service','User', getpass.getuser())

with open(f"{os.path.dirname(__file__)}/chappie.service", 'w') as f:
    config.write(f)

