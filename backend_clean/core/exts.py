"""Flask 扩展实例：独立创建 SQLAlchemy，避免循环导入。"""

from flask_sqlalchemy import SQLAlchemy

# 独立实例化，解决循环导入问题
db = SQLAlchemy()
