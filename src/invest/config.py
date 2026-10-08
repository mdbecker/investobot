import os
import tomllib
from pathlib import Path
from platformdirs import user_config_path, user_data_path

def load_config():
    path = Path(os.environ.get('INVEST_CONFIG', user_config_path('invest-copilot') / 'config.toml'))
    return tomllib.loads(path.read_text()) if path.exists() else {}

def database_path():
    return Path(os.environ.get('INVEST_DB', user_data_path('invest-copilot') / 'portfolio.db'))
