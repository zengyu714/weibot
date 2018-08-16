## 微博备份脚本

准备工作：
1. 安装Python3.6（其他版本未测试）及项目中使用的包。
2. 将`configuration.example.py`重命名为`configuration.py`并改为自己的**账号**，**密码**。

### Prerequisites

**Python 3.6**

Recommand [Miniconda3](https://conda.io/miniconda.html) for people rarely use Python.
Then Python 3.6 would be installed easily.

### Installing

1. Clone this repository

    ```bash
    cd /path/to/anywhere/you/like
    git clone https://github.com/zengyu714/weibot
    ```
    Now the directory looks like

    ```bash
    .
    ├── README.md
    ├── configuration.example.py
    ├── main.py
    ├── requirements.txt
    └── pages [directory]
        └── README.md

    ```

2. Install dependencies

    ```python
    pip install -r requirements.txt
    ```

### Running
1. 修改配置文件`configuration.example.py`
    + `CONFIG.weibo_account_username`
        修改为微博的登录名，如手机号，邮箱地址
        E.g., `CONFIG.weibo_account_username = "yourfather@me.com"`
    + `CONFIG.weibo_account_password`
       修改为微博的密码
       E.g., `CONFIG.weibo_account_password = "lovababa484"`

1. 将配置文件名称由`configuration.example.py`改成`configuration.py`，可以重命名，也可以用terminal
    ```bash
    mv configuration.example.py configuration.py
    ```
1. 运行`weibot.py`脚本
    ```python
    python weibot.py
    ```

**Note**
+ 生成`pages`文件夹保存微博json文件
+ 生成**结果文件**`mblog_backup_<current_date>.html`,可以在浏览器打开并打印成PDF

### Contributions
- [x] 评论，点赞好像没有必要备份
- [x] 优化备份页面排版

### License
This project is licensed under the MIT License
