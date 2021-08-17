import json
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
import requests
from bs4 import BeautifulSoup
from dateutil import parser
import time

HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/68.0.3440.106 Safari/537.36'
}
TIMEOUT = 8
# 网易云音乐的成立日期，不会有电台比这个更早
START_DATE = datetime(year=2013, month=4, day=23)


@dataclass()
class Program:
    """
    表示一个节目
    """

    index: int
    title: str
    count: int
    thumb: int
    date: datetime
    duration: timedelta


def get_html(url: str) -> str:
    """
    获取指定网址的 html 文档
    """
    req = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if req.status_code == 200:
        return req.text
    else:
        raise Exception(f'无法访问网址：{url}')


def get_radio_data(radio_id: str):
    """
    获取指定电台的基本信息
    """
    # 经由下列网址对电台中的节目列表进行访问
    # id 为电台的 id 编号
    # order 为节目排列顺序，默认为 1（新的在前），2 为旧的在前
    # limit 为每页最多显示的节目数量，默认 50，经测试最多支持 500
    # offset 表示节目编号的偏移量
    url = 'https://music.163.com/djradio?id={}&order={}&limit=500&offset={}'
    offset = 0
    order = 2  # 从旧到新
    page = get_html(url.format(radio_id, order, offset))
    soup = BeautifulSoup(page, 'html.parser')
    # 电台的基本信息
    radio_info_text = soup.find('textarea', id='radio-data')
    if not radio_info_text:
        return
    radio_info_json = json.loads(radio_info_text.text)

    program_count = int(radio_info_json['programCount'])
    program_data = get_page_program_data(soup)
    while offset + 500 < program_count:
        offset += 500
        page = get_html(url.format(radio_id, order, offset))
        soup = BeautifulSoup(page, 'html.parser')
        program_data.extend(get_page_program_data(soup))

    return radio_info_json, program_data


def get_page_program_data(soup: BeautifulSoup):
    """获取单页最多 500 个节目的列表"""
    page_data = []
    song_list = soup.find_all('tr',
                              id=lambda x: x and x.startswith('songlist'),
                              class_=True)

    def extract(line):
        cols = line.find_all('td')
        # 期数
        index = int(cols[0].find('span', class_='num').string)
        # 标题
        title = cols[1].div.a['title']
        # 播放数（形如 播放299，播放13万）
        count = cols[2].span.string[2:]
        if count.endswith('万'):
            count = count[:-1] + '5000'
        count = int(count)
        # 赞数（形如 赞1）
        thumb = int(cols[3].span.string[1:])
        # 上传日期（形如 2019-1-25）
        date = parser.parse(cols[4].span.string)
        # 节目时长（形如 99:31）
        m, s = tuple(map(int, cols[5].span.string.split(':')))
        duration = timedelta(minutes=m, seconds=s)
        return Program(index, title, count, thumb, date, duration)

    for line in song_list:
        page_data.append(extract(line))
    return page_data


def show_radio_info(info, programs):
    """展示电台基本信息"""
    # 时间
    start_date = ms_to_date(info['createTime'])
    first_date = programs[0].date
    last_date = ms_to_date(info['lastProgramCreateTime'])
    today = datetime.now()
    total_timespan = (today - start_date).days
    program_timespan = (last_date - first_date).days
    if program_timespan == 0:
        program_timespan += 1
    # 信息
    subCount = int(info['subCount'])
    programCount = int(info['programCount'])
    rcmdText = info['rcmdText']
    timeout = (today - last_date).days
    print('============= 基本信息 =============')
    print(f"电台名：{info['name']}，编号：{info['id']}")
    print(f"主播：{info['dj']['nickname']}")
    print(f"分类：{info['category']}")
    print(f"分享次数：{info['shareCount']}")
    print(f"订阅人数：{subCount}")
    if rcmdText:
        print(f"推荐语：{rcmdText}")
    print(f"节目数量：{programCount}")
    print(f"第一期：{first_date.date()}，最新一期：{last_date.date()}")
    print(f"共计更新{program_timespan}天", end='')
    if timeout >= 7:
        print(f"，目前已断更{timeout}天")
    else:
        print()
    print(f"更新频率：{float(programCount) / program_timespan:.3f} 期/天")
    print(f"更新周期：{float(program_timespan) / programCount:.3f} 天/期")
    print(f"创建日期：{start_date.date()}，距今 {(today - start_date).days} 天")
    print(f"日均涨粉数量：{int(info['subCount']) / total_timespan:.2f}")
    print('============= 统计信息 =============')
    # 节目时长
    durations = np.array([p.duration.seconds for p in programs])
    # 节目播放次数
    playbacks = np.array([p.count for p in programs])
    # 总播放次数
    total_playback = np.sum(playbacks)
    # 人均总播放次数
    playback_per_audience = total_playback / subCount
    # 平均每期播放次数
    playback_per_program = total_playback / programCount
    # 人均每期播放次数
    average_playback = playback_per_audience / programCount
    # 赞数
    thumbs = np.array([p.thumb for p in programs])
    total_thumbs = np.sum(thumbs)
    thumbs_per_audience = total_thumbs / subCount
    thumbs_per_program = total_thumbs / programCount
    print(f"总时长　：{timedelta(seconds=int(np.sum(durations)))}")
    print(f"平均时长：{timedelta(seconds=int(np.mean(durations)))}")
    print("---------------------------------")
    print(f"总播放量　　　　　：{total_playback}")
    print(f"人均总播放量　　　：{playback_per_audience:.2f}")
    print(f"平均每期节目播放量：{playback_per_program:.2f}")
    print(f"人均每期节目播放量：{average_playback:.2f}")
    print("---------------------------------")
    print(f"总赞数　　　：{total_thumbs}")
    print(f"人均总赞数　：{thumbs_per_audience:.2f}")
    print(f"平均每期赞数：{thumbs_per_program:.2f}")


def ms_to_date(ms):
    t = time.localtime(ms / 1000)
    d = datetime(*t[:6])
    return d


def main():
    id = input("请输入电台 id：")
    radio_info, program_data = get_radio_data(id)
    show_radio_info(radio_info, program_data)


if __name__ == "__main__":
    main()