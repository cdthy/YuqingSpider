# !/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'wtq'
import os
import sys

reload(sys)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.setdefaultencoding('utf-8')
import time
from datetime import datetime
import json
import chardet
import random
import logging
from scrapy import Request
from scrapy.spiders import Spider
from ..common.config import CRAWLER_TIME_SIGN
from ..common.config import SIGN_TIME_STAMP
from ..common.conn_mysql import conn_mysql
from ..common.searResultPages import searResultPages
from scrapy.selector import Selector
from ..util.transtime import transtime
from ..util.redis_queue import RedisQueue

# 'newsItem':[Item, Item, Item, Item]
content_queue = RedisQueue('items')  # 'newsContent':[{url:}]


class newsSpider(Spider):
    name = 'newsSpider'
    start_urls = []
    keyword = None
    searchEngine = None
    selector = None
    item_json = None

    def __init__(self, pages=1, *args, **kwargs):

        super(newsSpider, self).__init__(*args, **kwargs)
        # self.item = BaseItem()
        self.item = dict()
        # store the next latest time, crawl the news when the publish time bigger then it
        self.latest_time = dict()

        mysql_conn = conn_mysql()
        mysqlop = mysql_conn.cursor()
        mysqlop.execute("SET NAMES utf8")
        mysqlop.execute("SET CHARACTER_SET_CLIENT=utf8")
        mysqlop.execute("SET CHARACTER_SET_RESULTS=utf8")
        mysql_conn.commit()

        # get latest time from mysql
        mysqlop.execute("select source_name, latest_time, key_word from source_latest_time")
        times = mysqlop.fetchmany(size=10000000)
        for time_item in times:
            if time_item[0] not in self.latest_time:
                self.latest_time[time_item[0]] = dict()
            self.latest_time[time_item[0]][time_item[2]] = int(time.mktime(time_item[1].timetuple()))

        # get key words from mysql
        mysqlop.execute("select keyword from key_words")
        keywords = mysqlop.fetchmany(size=10000000)

        # get site template from mysql
        mysqlop.execute("select id, cn_name, url, template, page_type, type from t_source_used where type='news' and cn_name='百度新闻'")
        ses = mysqlop.fetchmany(size=10000000)

        for item in keywords:
            key_word = item[0]
            for se in ses:
                type_page = se[4]
                source_name = se[1]

                # source time and key word not in table, then put it latest time in one month before
                insert_sql = "insert into source_latest_time(latest_time, source_name, key_word) values(%s, %s, %s)"
                initialize_crawl_time = datetime.strptime(CRAWLER_TIME_SIGN, '%Y-%m-%d %H:%M:%S')
                if source_name not in self.latest_time.keys():
                    self.latest_time[source_name] = dict()
                    self.latest_time[source_name][key_word] = SIGN_TIME_STAMP
                    mysqlop.execute(insert_sql, (initialize_crawl_time, source_name, key_word))
                    mysql_conn.commit()
                elif key_word not in self.latest_time[source_name].keys():
                    self.latest_time[source_name][key_word] = SIGN_TIME_STAMP
                    mysqlop.execute(insert_sql, (initialize_crawl_time, source_name, key_word))
                    mysql_conn.commit()

                self.selector = json.loads(se[3])
                # 根据关键词与站点的名字与pages生成对应的不同的url
                pageUrls = searResultPages(key_word, se[2], 1, int(pages), type_page)

                # 不同页面的url存储到start_urls中,start_urls中的每个url都会调用parse函数执行
                for url in pageUrls:
                    print(url)
                    self.start_urls.append(
                        {'url': url, 'selector': self.selector, 'source_name': source_name, 'key_word': key_word,
                         'next_page': 2, 'type_page': type_page, 'source_url': se[2], 'type': se[5]})
        mysql_conn.close()
        mysqlop.close()
        random.shuffle(self.start_urls)

    def start_requests(self):
        for url in self.start_urls:
            yield Request(url['url'], meta={'selector': url['selector'], 'source_name': url['source_name'],
                                            'key_word': url['key_word'], 'next_page': url['next_page'],
                                            'type_page': url['type_page'], 'source_url': url['source_url'], 'type': url['type']})

    def parse(self, response):

        mysql_conn = conn_mysql()
        mysqlop = mysql_conn.cursor()
        self.selector = response.meta['selector']
        source_name = response.meta['source_name']
        source_url = response.meta['source_url']
        key_word = response.meta['key_word']
        next_page = response.meta['next_page']
        type_page = response.meta['type_page']
        source_type = response.meta['type']
        over_time_sign = 1
        first_item_sign = 1

        response = response.replace(body=response.body.replace('<em>', '').replace('</em>', ''))
        blocks = Selector(response).xpath(self.selector['block'])
        print 'blocks len', len(blocks)

        for block in blocks:
            link = block.xpath(self.selector['link']).extract()
            title = block.xpath(self.selector['title']).extract()
            source = block.xpath(self.selector['from']).extract()

            if not isinstance(self.selector['abstract'], list):
                abstract = block.xpath(self.selector['abstract']).extract()
            else:
                abstract = block.xpath(self.selector['abstract'][0]).extract()
                get_abstract = ''.join(abstract).strip()
                if len(get_abstract) < 3:
                    abstract = block.xpath(self.selector['abstract'][1]).extract()

            if self.selector.has_key('time'):
                try:
                    ctime = block.xpath(self.selector['time']).extract()[0]
                except Exception, e:
                    ctime = block.xpath(self.selector['time']).extract()

                try:
                    name = ''.join(source).strip()
                    if name:
                        name = name.split(" ")[0]
                    if source_type == 'news':
                        ctime = int(ctime)
                    else:
                        ctime = transtime(ctime)
                except Exception, e:
                    ctime = None

            else:
                try:
                    # print 'has no time'
                    string = ''.join(source).replace("\xc2\xa0", " ").split(' ', 1)
                    if len(string) >= 2:
                        ctime = transtime(string[1].strip().encode('utf-8'))
                        name = string[0].strip()
                    else:
                        ctime = None
                        name = source_name
                except Exception, e:
                    logging.error('extract time error', e)
                    ctime = None
                    name = source_name

            if ctime == None:
                # publish time 解析为空则设置为当前时间的unix时间戳
                ctime = int(time.time())

            if ctime > self.latest_time[source_name][key_word]:

                if next_page == 2 and first_item_sign == 1:
                    update_sql = "update source_latest_time set latest_time=%s where source_name=%s and key_word=%s"
                    new_latest_time = datetime.fromtimestamp(ctime)
                    mysqlop.execute(update_sql, (new_latest_time, source_name, key_word))
                    mysql_conn.commit()
                    first_item_sign = 0

                self.item['publish_time'] = ctime
                self.item['From'] = source_type  # 此处改为type对应论坛新闻博客
                self.item['source_name'] = source_name
                self.item['key_word'] = key_word
                self.item['catch_date'] = str(int(time.time()))
                self.item['site_name'] = name
                self.item['url'] = ''.join(link).strip()
                self.item['title'] = ''.join(title).strip()
                self.item['summary'] = ''.join(abstract).strip()
                self.item['site_url'] = response.url

                if self.item['url']:
                    self.item_json = json.dumps(self.item)
                    # item_queue.put(item_json)
                    yield Request(self.item['url'], meta={'item': self.item_json}, callback=self.parse_body)
            else:
                over_time_sign = 0
                break

        if over_time_sign and next_page < 100 and blocks and len(blocks) > 5:
            print 'in request next page'
            # that say the next page also in the time list
            next_page_url = searResultPages(key_word, source_url, next_page, next_page, type_page).currentUrl()
            print 'next page', next_page_url
            yield Request(next_page_url, meta={'selector': self.selector, 'source_name': source_name,
                                            'key_word': key_word, 'next_page': next_page + 1,
                                            'type_page': type_page, 'source_url': source_url, 'type': source_type})
        mysqlop.close()
        mysql_conn.close()

    def parse_body(self, response):
        """
        url_md5 as key, html body as value then save to redis
        :param response:
        :return:
        """
        item = response.meta['item']
        item = json.loads(item)
        body = response.body
        # 对html_body编码类型进行判断，不是unicode的进行转换
        if not isinstance(body, unicode):
            code_type = chardet.detect(body)['encoding']
            if code_type == 'GB2312':
                code_type = 'gbk'
            html_body = body.decode(code_type).encode('utf-8')
        else:
            html_body = body.encode('utf-8')

        item['html_body'] = html_body
        url_content = json.dumps(item)
        # url_content = item
        # url_content = item + '@' + body
        if len(body) > 5:
            content_queue.put(url_content)
        else:
            logging.info(response.url)
