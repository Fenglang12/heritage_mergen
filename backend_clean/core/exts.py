# exts.py
from flask_sqlalchemy import SQLAlchemy

# 独立实例化，解决循环导入问题
db = SQLAlchemy()
