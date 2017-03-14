# !/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'wtq'

import os
import sys
import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from analyse_model.analyse.accident_event import AccidentEvent
from analyse_model.util.conn_mysql import conn_mysql

mysql_conn = conn_mysql()
mysqlop = mysql_conn.cursor()
mysqlop.execute("SET NAMES utf8")
mysqlop.execute("SET CHARACTER_SET_CLIENT=utf8")
mysqlop.execute("SET CHARACTER_SET_RESULTS=utf8")
mysql_conn.commit()


def hot_event(input):
    """
    对于聚类好的每类中的item list判断是否整体对应超过了热点源的2／3，若是定义为热点事件并返回结果
    :param input: json格式 {depart_id:[[title, publish_time, source_name,  summary, url, itemid, docid],[],[],,,[]]}
    :return: {depart_id:[[title, summary, 相似item对应的provinceId list[id....id..], 相似item[source_name, title, publish_time, url, itemid, docid]], [title, summary, [provinceid,,,,,,provinceid,,,,,], [source_name, title, publish_time, url, itemid, docid]], [,,,,,], [,,,,,], []]}
    """
    input_list = []
    input_dict = {}
    select_item_sql = "select title, publish_time, province_id_list, summary, url, site_name, type from t_items where url_md5=%s"
    get_item_class = "select item_class from t_items where url_md5=%s"
    get_class_count = "select count(*) from t_items where item_class=%s"
    get_same_class_urlmd5 = "select url_md5 from t_items where item_class=%s"

    depart_id = input['reqData']['depart_id']
    new_cluster_result = []

    # 根据item_class将输入的input item划分类别
    for item in input['reqData']['items']:
        mysqlop.execute(get_item_class, [item['itemid']])
        item_class = mysqlop.fetchmany(1)[0][0]
        mysqlop.execute(get_class_count, [item_class])
        class_count = mysqlop.fetchmany(1)[0][0]

        if class_count > 9:
            mysqlop.execute(get_same_class_urlmd5, [item_class])
            class_md5 = mysqlop.fetchmany(100)
            temp_class = []
            for i in class_md5:
                temp_class.append(i[0])
            # 同一类的url_md5存在同一个list中，作为一个元素存到new_cluster_result中
            new_cluster_result.append(temp_class)
            # 获取每个item的其他信息存到item_dict中
            for urlmd5 in temp_class:
                temp = []
                mysqlop.execute(select_item_sql, [urlmd5])
                select_item = mysqlop.fetchmany(size=1)[0]
                temp.append(select_item[0])
                temp.append(select_item[1])
                temp.append(urlmd5)
                temp.append(select_item[2])
                temp.append(select_item[3])
                temp.append(select_item[4])
                temp.append(select_item[5])
                temp.append(item['docid'])
                temp.append(select_item[6])
                input_list.append(temp)
                input_dict[urlmd5] = temp

    response_data = {}
    response_data['sid'] = input['sid']
    response_data['resData'] = {}
    response_data['resData']['depart_id'] = depart_id
    response_data['resData']['hotList'] = []

    for class_item in new_cluster_result:

        temp_dict = {}
        # 聚类结果第一条的title summary作为该类的title summary的代表
        temp_dict['title'] = input_dict[class_item[0]][0]
        temp_dict['summary'] = input_dict[class_item[0]][4]
        temp_dict['provinceIdList'] = ""
        temp_dict['relativeItems'] = []
        print 'class_item', class_item

        for i in class_item:
            sub_dict = {}
            if input_dict[i][3]:
                province_ids = input_dict[i][3].split(",")
                for p_id in province_ids:
                    if p_id and p_id not in temp_dict['provinceIdList']:
                        temp_dict['provinceIdList'] += p_id + ","

            sub_dict['source_name'] = input_dict[i][6]
            sub_dict['title'] = input_dict[i][0]
            sub_dict['publish_time'] = str(input_dict[i][1])
            sub_dict['url'] = input_dict[i][5]
            sub_dict['itemid'] = i
            sub_dict['docid'] = input_dict[i][7]
            sub_dict['type'] = input_dict[i][8]
            temp_dict['relativeItems'].append(sub_dict)

        # print temp_dict
        response_data['resData']['hotList'].append(temp_dict)
    return response_data


if __name__ == "__main__":
    mysqlop.execute("select title, publish_time, url_md5, source_name, type, url, summary from t_items where item_class is not null")
    items = mysqlop.fetchmany(size=100)
    inputs = {}
    print len(items)
    inputs['sid'] = 5
    inputs['reqData'] = {}
    inputs['reqData']['items'] = []
    inputs['reqData']['depart_id'] = 1
    input_item = []
    for item in items:
        temp_dict = {}
        temp_dict['title'] = item[0]
        temp_dict['publish_time'] = str(item[1])
        temp_dict['itemid'] = item[2]
        input_item.append(item[2])
        temp_dict['source_name'] = item[3]
        temp_dict['type'] = item[4]
        temp_dict['url'] = item[5]
        temp_dict['summary'] = item[6]
        temp_dict['docid'] = 3
        temp_dict['province_id'] = 1
        inputs['reqData']['items'].append(temp_dict)
    hot_event(inputs)

