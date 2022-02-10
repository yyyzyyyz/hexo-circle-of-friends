# -*- coding:utf-8 -*-

import datetime
import os
import time
import scrapy
import queue
import feedparser
from scrapy.http.request import Request
from hexo_circle_of_friends import settings
from bs4 import BeautifulSoup
from hexo_circle_of_friends.utils.get_url import get_theme_url, Yun_async_link_handler
from hexo_circle_of_friends.utils.regulations import *
from hexo_circle_of_friends.utils.process_time import format_time


# from hexo_circle_of_friends import items todo use items
class FriendpageLinkSpider(scrapy.Spider):
    name = 'hexo_circle_of_friends'
    allowed_domains = ['*']
    start_urls = []

    def __init__(self, name=None, **kwargs):
        self.friend_poor = queue.Queue()
        self.friend_list = queue.Queue()
        self.today = datetime.datetime.now().strftime('%Y-%m-%d')

        super().__init__(name, **kwargs)

    def start_requests(self):
        # 从配置文件导入友链列表
        if settings.SETTINGS_FRIENDS_LINKS['enable']:
            for li in settings.SETTINGS_FRIENDS_LINKS["list"]:
                # user_info = [li[0],li[1],li[2]]
                # print('----------------------')
                # print('好友名%r' % li[0])
                # print('头像链接%r' % li[2])
                # print('主页链接%r' % li[1])
                self.friend_poor.put(li)
        if settings.GITEE_FRIENDS_LINKS['enable']:
            for number in range(1, 100):
                domain = 'https://gitee.com'
                dic = settings.GITEE_FRIENDS_LINKS
                url = domain + "/" + dic["owner"] + "/" + dic["repo"] + '/issues?state=' + dic[
                    "state"] + '&page=' + str(number)
                yield Request(url, callback=self.friend_poor_parse, meta={"gitee": {"domain": domain}})
        if settings.GITHUB_FRIENDS_LINKS['enable']:
            for number in range(1, 100):
                domain = 'https://github.com'
                dic = settings.GITHUB_FRIENDS_LINKS
                url = domain + "/" + dic["owner"] + "/" + dic["repo"] + "/issues?q=is%3A" + dic[
                    "state"] + '&page=' + str(number)
                yield Request(url, callback=self.friend_poor_parse, meta={"github": {"domain": domain}})
        if settings.DEBUG:
            friendpage_link = settings.FRIENDPAGE_LINK
        else:
            friendpage_link = []
            friendpage_link.append(os.environ["LINK"])
            if settings.EXTRA_FRIENPAGE_LINK:
                friendpage_link.extend(settings.EXTRA_FRIENPAGE_LINK)

        self.start_urls.extend(friendpage_link)
        for url in self.start_urls:
            yield Request(url, callback=self.friend_poor_parse, meta={"theme": url})

    def friend_poor_parse(self, response):
        # 获取朋友列表
        # print("friend_poor_parse---------->" + response.url)

        if "gitee" in response.meta.keys():
            main_content = response.css("#git-issues a.title::attr(href)").extract()
            if main_content:
                for item in main_content:
                    issueslink = response.meta["gitee"]["domain"] + item
                    yield Request(issueslink, self.friend_poor_parse, meta={"gitee-issues": None}, dont_filter=True)
        if "gitee-issues" in response.meta.keys():
            try:
                content = ''.join(response.css("code *::text").extract())
                user_info = []
                if settings.GITHUB_FRIENDS_LINKS["type"] == "volantis":
                    reg_volantis(user_info, content)
                    self.friend_poor.put(user_info)
                else:
                    info_list = ['name', 'link', 'avatar']
                    reg_normal(info_list, user_info, content)
                    if user_info[1] != '你的链接':
                        self.friend_poor.put(user_info)
            except:
                pass

        if "github" in response.meta.keys():
            main_content = response.css("div[aria-label=Issues] a.Link--primary::attr(href)").extract()
            if main_content:
                for item in main_content:
                    issueslink = response.meta["github"]["domain"] + item
                    yield Request(issueslink, self.friend_poor_parse, meta={"github-issues": None}, dont_filter=True)
        if "github-issues" in response.meta.keys():
            try:
                content = ''.join(response.css("pre *::text").extract())
                if content != '':
                    user_info = []
                    if settings.GITHUB_FRIENDS_LINKS["type"] == "volantis":
                        reg_volantis(user_info, content)
                        self.friend_poor.put(user_info)
                    else:
                        info_list = ['name', 'link', 'avatar']
                        reg_normal(info_list, user_info, content)
                        if user_info[1] != '你的链接':
                            self.friend_poor.put(user_info)
            except:
                pass

        if "theme" in response.meta.keys():
            if settings.FRIENDPAGE_STRATEGY["strategy"] == "default":
                theme = settings.FRIENDPAGE_STRATEGY["theme"]
                async_link = get_theme_url(theme, response, self.friend_poor)
                if async_link:
                    # Yun主题的async_link临时解决
                    yield Request(async_link, callback=self.friend_poor_parse, meta={"async_link": async_link},
                                  dont_filter=True)
            else:
                pass
        if "async_link" in response.meta.keys():
            Yun_async_link_handler(response, self.friend_poor)

        # 要添加主题扩展，在这里添加一个请求
        while not self.friend_poor.empty():
            friend = self.friend_poor.get()
            friend[1] += "/" if not friend[1].endswith("/") else ""
            if settings.SETTINGS_FRIENDS_LINKS['enable'] and len(friend) == 4:
                url = friend[1] + friend[3]
                yield Request(url, callback=self.post_feed_parse, meta={"friend": friend}, dont_filter=True,
                              errback=self.errback_handler)
                self.friend_list.put(friend[:3])
                continue
            self.friend_list.put(friend)
            yield Request(friend[1] + "atom.xml", callback=self.post_feed_parse, meta={"friend": friend},
                          dont_filter=True, errback=self.errback_handler)
            yield Request(friend[1] + "feed/atom", callback=self.post_feed_parse, meta={"friend": friend},
                          dont_filter=True, errback=self.typecho_errback_handler)
            yield Request(friend[1] + "rss.xml", callback=self.post_feed_parse, meta={"friend": friend},
                          dont_filter=True, errback=self.errback_handler)
            yield Request(friend[1] + "rss2.xml", callback=self.post_feed_parse, meta={"friend": friend},
                          dont_filter=True, errback=self.errback_handler)
            yield Request(friend[1] + "feed", callback=self.post_feed_parse, meta={"friend": friend},
                          dont_filter=True, errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_butterfly_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_fluid_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_matery_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_sakura_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_volantis_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_nexmoe_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_Yun_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_stun_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)
            yield Request(friend[1], callback=self.theme_stellar_parse, meta={"friend": friend}, dont_filter=True,
                          errback=self.errback_handler)

        # friend = ['小冰博客', 'https://shujin.fun/', 'https://zfe.space/images/headimage.png']
        # [[1,1,1],[2,3,2]]
        # yield Request(friend[1], callback=self.theme_stellar_parse, meta={"friend": friend}, dont_filter=True,
        #               errback=self.errback_handler)

        # 将获取到的朋友列表传递到管道
        while not self.friend_list.empty():
            friend = self.friend_list.get()
            userdata = {}
            userdata["name"] = friend[0]
            userdata["link"] = friend[1]
            userdata["img"] = friend[2]
            userdata["userdata"] = "userdata"
            yield userdata

    def post_feed_parse(self, response):
        # print("post_feed_parse---------->" + response.url)
        friend = response.meta.get("friend")
        d = feedparser.parse(response.text)
        version = d.version
        entries = d.entries
        l = len(entries) if len(entries) < 5 else 5
        try:
            init_post_info = self.init_post_info(friend, version)
            for i in range(l):
                entry = entries[i]
                # 标题
                title = entry.title
                # 链接
                link = entry.link
                self.process_link(link, friend[1])
                # 创建时间
                try:
                    created = entry.published_parsed
                except:
                    try:
                        created = entry.created_parsed
                    except:
                        created = entry.updated_parsed
                entrycreated = "{:4d}-{:02d}-{:02d}".format(created[0], created[1], created[2])
                # 更新时间
                try:
                    updated = entry.updated_parsed
                except:
                    try:
                        updated = entry.created_parsed
                    except:
                        updated = entry.published_parsed
                entryupdated = "{:4d}-{:02d}-{:02d}".format(updated[0], updated[1], updated[2])

                yield self.generate_postinfo(
                    init_post_info,
                    title,
                    entrycreated,
                    entryupdated,
                    link
                )
        except:
            pass

    def post_atom_parse(self, response):
        # print("post_atom_parse---------->" + response.url)
        friend = response.meta.get("friend")
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("entry")
        if items:
            if 0 < len(items) < 5:
                l = len(items)
            else:
                l = 5
            try:
                for i in range(l):
                    post_info = {}
                    item = items[i]
                    title = item.find("title").text
                    url = item.find("link")['href']
                    date = item.find("published").text[:10]
                    updated = item.find("updated").text[:10]
                    post_info['title'] = title
                    post_info['time'] = date
                    post_info['updated'] = updated
                    post_info['link'] = url
                    post_info['name'] = friend[0]
                    post_info['img'] = friend[2]
                    post_info['rule'] = "atom"
                    yield post_info
            except:
                pass

    def post_rss2_parse(self, response):
        # print("post_rss2_parse---------->" + response.url)
        friend = response.meta.get("friend")
        sel = scrapy.Selector(text=response.text)
        title = sel.css("item title::text").extract()
        link = sel.css("item guid::text").extract()
        pubDate = sel.css("item pubDate::text").extract()
        if len(link) > 0:
            l = len(link) if len(link) < 5 else 5
            try:
                for i in range(l):
                    m = pubDate[i].split(" ")
                    ts = time.strptime(m[3] + "-" + m[2] + "-" + m[1], "%Y-%b-%d")
                    date = time.strftime("%Y-%m-%d", ts)
                    if link[i].startswith("/"):
                        link[i] = friend[1] + link[i].split("/", 1)[1]
                    post_info = {
                        'title': title[i],
                        'time': date,
                        'updated': date,
                        'link': link[i],
                        'name': friend[0],
                        'img': friend[2],
                        'rule': "rss"
                    }
                    yield post_info
            except:
                pass

    def post_wordpress_parse(self, response):
        # print("post_wordpress_parse---------->" + response.url)
        friend = response.meta.get("friend")
        sel = scrapy.Selector(text=response.text)
        title = sel.css("item title::text").extract()
        link = [comm.split("#comments")[0] for comm in sel.css("item link+comments::text").extract()]
        pubDate = sel.css("item pubDate::text").extract()
        if len(link) > 0:
            l = len(link) if len(link) < 5 else 5
            try:
                for i in range(l):
                    m = pubDate[i].split(" ")
                    ts = time.strptime(m[3] + "-" + m[2] + "-" + m[1], "%Y-%b-%d")
                    date = time.strftime("%Y-%m-%d", ts)
                    post_info = {
                        'title': title[i],
                        'time': date,
                        'updated': date,
                        'link': link[i],
                        'name': friend[0],
                        'img': friend[2],
                        'rule': "wordpress"
                    }
                    yield post_info
            except:
                pass

    def theme_butterfly_parse(self, response):
        # print("theme_butterfly_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("#recent-posts .recent-post-info>a::text").extract()
        partial_l = response.css("#recent-posts .recent-post-info>a::attr(href)").extract()
        createds = response.css("#recent-posts .recent-post-info .post-meta-date-created::text").extract()
        updateds = response.css("#recent-posts .recent-post-info .post-meta-date-updated::text").extract()
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "butterfly")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_fluid_parse(self, response):
        # print("theme_fluid_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("#board .index-header a::text").extract()
        partial_l = response.css("#board .index-header a::attr(href)").extract()
        createds = response.css("#board .post-meta time::text").extract()
        updateds = []
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "fluid")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_matery_parse(self, response):
        # print("theme_matery_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("#articles .card .card-title::text").extract()
        partial_l = response.css("#articles .card a:first-child::attr(href)").extract()
        createds = response.css("#articles .card span.publish-date").re("\d{4}-\d{2}-\d{2}")
        updateds = []
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "matery")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_sakura_parse(self, response):
        # print("theme_sakura_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("#main a.post-title h3::text").extract()
        if not titles:
            res = re.findall("<body.*</body>", response.text)
            if res:
                text = res[0]
                sel = scrapy.Selector(text=text)
                titles = sel.css("body #main a.post-title h3::text").extract()
                links = sel.css("#main a.post-title::attr(href)").extract()
                createds = sel.css("#main .post-date::text").re("\d{4}-\d{1,2}-\d{1,2}")
            else:
                return
        else:
            links = response.css("#main a.post-title::attr(href)").extract()
            createds = response.css("#main .post-date::text").re("\d{4}-\d{1,2}-\d{1,2}")
        updateds = []
        try:
            l = len(links) if len(links) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "sakura")
            for i in range(l):
                link = self.process_link(links[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_volantis_parse(self, response):
        # print("theme_volantis_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css(".post-list .article-title a::text").extract()
        partial_l = response.css(".post-list .article-title a::attr(href)").extract()
        createds = response.css(".post-list .meta-v3 time::text").extract()
        updateds = []
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "volantis")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_nexmoe_parse(self, response):
        # print("theme_nexmoe_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("section.nexmoe-posts .nexmoe-post h1::text").extract()
        partial_l = response.css("section.nexmoe-posts .nexmoe-post>a::attr(href)").extract()
        createds = response.css("section.nexmoe-posts .nexmoe-post-meta a:first-child::text").extract()
        updateds = []
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "nexmoe")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_Yun_parse(self, response):
        # print("theme_Yun_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("article .post-title a::text").extract()
        links = response.css("article link::attr(href)").extract()
        createds = response.css("article time[itemprop*=dateCreated]::text").extract()
        updateds = response.css("article time[itemprop=dateModified]::text").extract()
        try:
            l = len(links) if len(links) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "Yun")
            for i in range(l):
                link = self.process_link(links[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_stun_parse(self, response):
        # print("theme_stun_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css("article .post-title__link::text").extract()
        partial_l = response.css("article .post-title__link::attr(href)").extract()
        createds = response.css("article .post-meta .post-meta-item--createtime .post-meta-item__value::text").extract()
        updateds = response.css("article .post-meta .post-meta-item--updatetime .post-meta-item__value::text").extract()
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "stun")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def theme_stellar_parse(self, response):
        # print("theme_stellar_parse---------->" + response.url)
        friend = response.meta.get("friend")
        titles = response.css(".post-list .post-title::text").extract()
        partial_l = response.css(".post-list .post-card::attr(href)").extract()
        createds = response.css("#post-meta time::attr(datetime)").extract()
        updateds = []
        try:
            l = len(partial_l) if len(partial_l) < 5 else 5
            titles = self.process_title(titles, l)
            createds, updateds = self.process_time(createds, updateds, l)
            init_post_info = self.init_post_info(friend, "stellar")
            for i in range(l):
                link = self.process_link(partial_l[i], friend[1])
                yield self.generate_postinfo(
                    init_post_info,
                    titles[i],
                    createds[i] if createds else self.today,
                    updateds[i] if updateds else self.today,
                    link
                )
        except:
            pass

    def init_post_info(self, friend, rule):
        post_info = {
            "name": friend[0],
            "img": friend[2],
            "rule": rule
        }
        return post_info

    def process_link(self, link, domain):
        # 将link处理为标准链接
        if not re.match("^http.?://", link):
            link = domain + link.lstrip("/")
        return link

    def process_title(self, titles, lenth):
        # 将title去除换行和回车以及两边的空格，并处理为长度不超过lenth的数组并返回
        if not titles:
            return None
        for i in range(lenth):
            if i < len(titles):
                titles[i] = titles[i].replace("\r", "").replace("\n", "").strip()
            else:
                titles.append("无题")
        return titles[:lenth]

    def process_time(self, createds, updateds, lenth):
        # 将创建时间和更新时间格式化，并处理为长度统一且不超过lenth的数组并返回
        if not createds and not updateds and not lenth:
            return None, None
        c_len = len(createds)
        u_len = len(updateds)
        co = min(c_len, u_len)
        for i in range(lenth):
            if i < co:
                createds[i] = createds[i].replace("\r", "").replace("\n", "").strip()
                updateds[i] = updateds[i].replace("\r", "").replace("\n", "").strip()
            elif i < u_len:
                updateds[i] = updateds[i].replace("\r", "").replace("\n", "").strip()
                createds.append(updateds[i])
            elif i < c_len:
                createds[i] = createds[i].replace("\r", "").replace("\n", "").strip()
                updateds.append(createds[i])
            else:
                createds.append(self.today)
                updateds.append(self.today)

        format_time(createds)
        format_time(updateds)
        return createds[:lenth], updateds[:lenth]

    def generate_postinfo(self, init_post_info, title, created, updated, link):
        post_info = init_post_info
        post_info["title"] = title
        post_info["time"] = created
        post_info["updated"] = updated
        post_info["link"] = link
        return post_info

    def errback_handler(self, error):
        # 错误回调
        # todo error???
        # print("errback_handler---------->")
        # print(error)
        # request = error.request
        # meta = error.request.meta
        pass

    def typecho_errback_handler(self, error):
        yield Request(error.request.url, callback=self.post_feed_parse, dont_filter=True, meta=error.request.meta,
                      errback=self.errback_handler)
