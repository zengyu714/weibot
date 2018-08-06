import base64
import binascii
import json
import random
import re
import time
from pathlib import Path
from urllib import parse

import requests
import rsa
from bs4 import BeautifulSoup
from tqdm import tqdm
from yattag import Doc

from configuration import CONF


class WeiBot:
    session = requests.Session()

    def __init__(self,
                 username=CONF.weibo_account_username,
                 password=CONF.weibo_account_password,
                 pages_cache_dir="pages",
                 debug=False):
        self.debug = debug
        self.pages_cache_dir = Path(pages_cache_dir)
        self.headers = {
            "User-Agent"     : "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0",
            "Accept-Language": "zh"
        }

        # login
        self.username = self.get_username(username)
        self.server_data = self.get_server_data()
        self.password = self.get_password(password)

        # user info
        self.uniqueid = None
        self.nickname = None

    @staticmethod
    def get_username(plain_username):
        """encrypt username (email/phone)"""

        username_quote = parse.quote_plus(plain_username).encode("utf-8")
        username_base64 = base64.b64encode(username_quote)
        return username_base64.decode("utf-8")

    def get_server_data(self):
        pre_url = "https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su="
        pre_url = pre_url + self.username + "&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_="
        prelogin_url = pre_url + str(int(time.time() * 1000))
        pre_data = requests.get(prelogin_url, headers=self.headers).content.decode("utf-8")
        return eval(pre_data.replace("sinaSSOController.preloginCallBack", ''))

    def get_password(self, plain_password):
        rsa_public_key = int(self.server_data["pubkey"], 16)
        key = rsa.PublicKey(rsa_public_key, 65537)
        msg = str(self.server_data["servertime"]) + "\t"
        msg += str(self.server_data["nonce"]) + "\n"
        msg += str(plain_password)
        password = rsa.encrypt(msg.encode("utf-8"), key)
        return binascii.b2a_hex(password)

    def gen_post_data(self):
        return {
            "entry"     : "weibo",
            "gateway"   : "1",
            "from"      : '',
            "savestate" : "7",
            "useticket" : "1",
            "pagerefer" : "https://login.sina.com.cn/sso/logout.php?entry=miniblog&r=http%3A%2F%2Fweibo.com%2Flogout.php%3Fbackurl",
            "vsnf"      : "1",
            "su"        : self.username,
            "service"   : "miniblog",
            "servertime": str(self.server_data["servertime"]),
            "nonce"     : self.server_data["nonce"],
            "pwencode"  : "rsa2",
            "rsakv"     : self.server_data["rsakv"],
            "sp"        : self.password,
            "sr"        : "1920*1080",
            "encoding"  : "UTF-8",
            "prelt"     : "158",
            "url"       : "https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack",
            "returntype": "META"
        }

    def login_pc(self):
        log_fence = "#" * 50
        print(f"===> PC Logging...\n{log_fence}")
        login_url = f"https://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.19)&_={int(time.time())}"
        login_response = self.session.post(login_url, params=self.gen_post_data(), headers=self.headers)

        redirect_result = login_response.content.decode("gbk")
        pat = r'location\.replace\([\'"](.*?)[\'"]\)'
        redirect_url = re.findall(pat, redirect_result)[0]
        redirect_text = self.session.get(redirect_url, headers=self.headers).content.decode("gbk")

        json_pat = r'{[\'"]retcode[\'"](.*?)}'
        json_data = json.loads(re.search(json_pat, redirect_text).group(0))
        arrurl = json_data["arrURL"][0]
        if json_data["retcode"] == 0:
            user_response = self.session.get(arrurl, headers=self.headers).content.decode("gbk")
            user_json = json.loads(re.findall(r"\((.*?)\);\s+", user_response)[0])
            if user_json["result"]:
                user_info = user_json["userinfo"]
                self.uniqueid = user_info["uniqueid"]
                self.nickname = user_info["displayname"]
                print(f"<< Success! >>\nUser ID:\t{self.uniqueid}\nNickname:\t{self.nickname}\n{log_fence}\n\n")
                return True
            else:
                print(f">> Oops... <<\nSomething wrong:\t{user_json}\n{log_fence}\n\n")
        return False

    def login_mob(self):
        """
        Login from pc cookies
        Ref: https://github.com/xchaoinfo/fuck-login/blob/master/003%20weibo.cn/m.weibo_jump_from_com.py
        """

        if not self.login_pc():
            return

        params = {
            "url"            : "https://m.weibo.cn/",
            "_rand"          : str(time.time()),
            "gateway"        : "1",
            "service"        : "sinawap",
            "entry"          : "sinawap",
            "useticket"      : "1",
            "returntype"     : "META",
            "sudaref"        : "",
            "_client_version": "0.6.26",
        }
        url = "https://login.sina.com.cn/sso/login.php"
        response = self.session.get(url,
                                    params=params,
                                    headers=self.headers.update({"Host": "login.sina.com.cn"}))
        response.encoding = response.apparent_encoding
        pat = r'replace\((.*?)\);'
        redirect_url = re.findall(pat, response.text)[0]

        self.session.get(eval(redirect_url),
                         headers=self.headers.update({"Host": "passport.weibo.cn"}))

        url = "https://m.weibo.cn"
        response = self.session.get(url,
                                    headers=self.headers.update({"Host": "m.weibo.cn"}))
        pat_login = r'login: \[1\]'
        login_res = re.findall(pat_login, response.text)

        if login_res:
            print(f"===> Mobile Logging...\t<< Success! >>")
            return True
        else:
            print(f">> Oops...Mobile Logging...\t<< Failed! >>")
            return False

    def cache_mob_pages(self):
        if not self.login_mob():
            return
        # create cache directory
        pages_dir = self.pages_cache_dir
        if not pages_dir.exists():
            pages_dir.mkdir()

        page_idx = 1
        url_template = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={self.uniqueid}&containerid=107603{self.uniqueid}&page="
        response = self.session.get(url_template + str(page_idx))

        entries_num = json.loads(response.text)["data"]["cardlistInfo"]["total"]
        pages_num = entries_num // 10 + 1
        print(f"===> Saving {entries_num} entries (default {pages_num} pages)...")

        # save json contents in `pages_dir`
        for page_i in tqdm(range(1, pages_num + 1)):
            response = json.loads(self.session.get(url_template + str(page_i)).text)
            with open("{}/page_content_{:03d}".format(pages_dir, page_i), "w+") as f:
                json.dump(response, f)

            # randomly sleep [0, 1] second
            time.sleep(random.random())

    @staticmethod
    def _get_text(response):
        pat = r'"text": (.*?),\s+"textLength"'
        long = re.findall(pat, response)
        try:
            text = eval(long[0])
        except IndexError:
            text = 'Empty'
        return text

    def _parse_card(self, mblog):
        info = {
            'name'       : mblog['user']['screen_name'],
            'source'     : mblog['source'],
            'create_time': mblog['created_at'],
            'text'       : mblog['text'],

            'mid'        : mblog['mid'],
            'is_long'    : mblog['isLongText'],
            'has_retweet': mblog['retweeted_status'] if 'retweeted_status' in mblog else None,
            'has_pic'    : mblog['pics'] if "pics" in mblog else None,

            # 'comments_count' : mblog['comments_count'],
            # 'attitudes_count': mblog['attitudes_count'],
        }

        if not info['is_long'] and not info['has_retweet']:
            return info

        # jump to status page
        url = f"https://m.weibo.cn/status/{mblog['mid']}"
        response = self.session.get(url).text
        if info['is_long']:
            info.update({'text': self._get_text(response)})
        return info

    def generate_html(self):
        if self.debug:
            pages = sorted(list(self.pages_cache_dir.glob('page_content_*')))
        else:
            self.cache_mob_pages()
            pages = sorted(list(self.pages_cache_dir.glob('page_content_*')))

        print(f"===> Generating HTML...\n")

        doc, tag, text, line = Doc().ttl()
        doc.asis('<!DOCTYPE html>')

        def _display_emoji(doc, tag, emoji):
            with tag('span', klass='emoji'):
                doc.stag('img',
                         src='http:' + emoji.get('src'),
                         klass='span_image',
                         style=emoji.get('style'))

        def _display_text(doc, tag, text, info):
            with tag('div', klass='mblog_info'):
                text('{} @ {} << {}'.format(
                    info['name'], info['create_time'], info['source']))
            with tag('div', klass='mblog_text'):
                # parse text
                html = info['text']
                soup = BeautifulSoup(html, 'lxml')
                soup_it = soup.descendants
                for descendant in soup_it:
                    # 1. plain text
                    if isinstance(descendant, str):
                        text(descendant)
                    # 2. blank line
                    elif descendant.name == 'br':
                        doc.stag('br')
                    # 3. images
                    elif descendant.attrs:
                        # embedded url, E.g., "查看图片" / "秒拍视频"
                        is_url = descendant.get('data-url')
                        if is_url and descendant.text:
                            _display_emoji(doc, tag, descendant.img)
                            with tag('a', href=is_url):
                                text(descendant.text)
                            [next(soup_it) for _ in range(4)]

                        # emoji
                        is_emoji = descendant.get('class')
                        if is_emoji and 'url-icon' in is_emoji:
                            emoji = descendant.contents[0]
                            _display_emoji(doc, tag, emoji)
                            next(soup_it)

        def _display_images(tag, info):
            if info['has_pic']:
                for pic in info['has_pic']:
                    with tag('span', klass='mblog_image'):
                        doc.stag('img', src=pic['url'], klass='span_image', style="margin-top: 1em;")

        with tag('html'):
            with tag('body'):
                line('h3', 'Backup @ {}'.format(time.ctime()))

                for p in tqdm(pages):
                    with p.open('r') as f:
                        contents = json.loads(f.read())['data']['cards']

                    for card in contents:
                        mblog = card['mblog']
                        info = self._parse_card(mblog)
                        if info['has_retweet']:
                            retweet = info['has_retweet']
                            try:
                                info.update({'has_retweet': self._parse_card(retweet)})

                            except TypeError:
                                info.update({'text': info['text'] + retweet['text']})
                                # print(retweet)
                                info.update({'has_retweet': None})

                        # deliminator
                        # ================================================================================
                        doc.stag('hr')

                        _display_text(doc, tag, text, info)
                        _display_images(tag, info)

                        if info['has_retweet']:
                            # retweet deliminator
                            with tag('div', klass='mblog_text',
                                     style="border-style: dashed none dashed none; width=100%; margin: 1em 0;"):
                                text('Retweet')

                            retweet = info['has_retweet']
                            _display_text(doc, tag, text, retweet)
                            _display_images(tag, retweet)

                        # deliminator
                        doc.stag('hr')
                        # ================================================================================

        backup = doc.getvalue()
        with open('mblog_backup_{}.html'.format(
                time.strftime("%Y%m%d", time.localtime())), 'w+', encoding='utf-8') as f:
            f.write(backup)

        print('  Backup Done ~~  '.center(50, '#'))


if __name__ == '__main__':
    wb = WeiBot()
    wb.generate_html()
