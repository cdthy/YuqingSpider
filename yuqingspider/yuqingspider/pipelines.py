# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
import sys
reload(sys)
sys.setdefaultencoding("utf-8")
import redis
import urllib2
import MySQLdb
from common.conn_mysql import conn_mysql
from common.conn_mongo import client_mongo
from common.md5 import md5


class YuqingspiderPipeline(object):

    def __init__(self):
        # mysql
        self.conn = MySQLdb.connect(host='localhost', port=3306, user='root', passwd='123', db='yuqing')
        self.mysqlop = self.conn.cursor()
        # redis
        self.r_conn = redis.StrictRedis(host='localhost', port=6379, db=0)
        # mongoDB
        client = client_mongo()
        self.db = client.spider

    def open_spider(self, spider):
        """This method is called when the spider is opened."""
        pass

    def process_item(self, item, spider):
        """
        deal the item which get from TencentSpider.parse_item
        :param item:
        :param spider:
        :return:
        """
        try:
            # html_body save into redis, item save into mysql
                # html_body = urllib2.urlopen(item['url'])
            url_md5 = md5(item['url'])
            # self.r_conn.set(url_md5, html_body.read())
            # item['html_body'] = None

            sqli = "insert into spider_content values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            news = {'content': item}
            # self.db.news.insert(news)

            if item['From'] == '0':
                # self.mysqlop.execute("insert into spider_content values('url_md5')")
                self.mysqlop.execute(sqli, (url_md5, None, item['spider_name'], item['catch_date'],
                                            item['From'], item['url'], item['title'].encode('utf-8'), item['summary'].encode('utf-8'), item['site_url'],
                                            None, None, None, item['site_name'].encode('utf-8')))


                self.db.emergency.insert(news)
            elif item['From'] == '1':
                # self.mysqlop.execute(sqli, (url_md5, item['publish_time'], item['spider_name'], item['catch_date'],
                #                             item['From'], item['url'], item['title'].encode('utf-8'), item['summary'].encode('utf-8'), item['site_url'],
                #                             None, None, None, item['site_name'].encode('utf-8')))

                self.db.news.insert(news)
            elif item['From'] == '2':

                self.mysqlop.execute(sqli, (url_md5, item['publish_time'], item['spider_name'], item['catch_date'],
                                            item['From'], item['url'], item['title'].encode('utf-8'), item['summary'].encode('utf-8'), item['site_url'],
                                            item['author'].encode('utf-8'), item['replay_times'], item['view_times'], item['site_name'].encode('utf-8')))
                self.db.bbs.insert(news)

                # 提交duimysql操作的事物

        except Exception, e:
            print 'pipeline error', e

    def close_spider(self, spider):
        self.mysqlop.close()
        self.conn.commit()
        self.conn.close()
        pass

if __name__ == "__main__":
    print '\xe5\xa4\xa9\xe5\xa4\xa9'.encode('utf8')

