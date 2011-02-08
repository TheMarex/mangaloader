#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import re
import os
import sys
import os.path as path
import urllib2
import difflib
import subprocess
import shlex
import time
import threading

from zipper import Zipper

HOME_DIR = os.environ['HOME']
MANGA_DIR = path.join(HOME_DIR, "Bücher/Mangas/")

class Page:
    _search_cache = None
    _chapter_cache = None
    _image_cache = None
    _page_cache = None
    #define in child class
    _search_exp = ""
    _search_url = ""
    _chapter_exp = ""
    _image_exp = ""
    _page_exp = ""

    def __init__(self):
        pass

    # define in child class
    def _handle_search_data(self, data):
        pass
    def _handle_image_data(self, data):
        pass
    def _handle_chapter_data(self, data, url):
        pass
    def _handle_page_data(self, data, url):
        pass

    def search_manga(self, name):
        mangas = self.get_mangas()
        if name in mangas:
            return [name]

        names = mangas.keys()
        return difflib.get_close_matches(name, names)[:3]

    def get_mangas(self):
        if self._search_cache:
            return self._search_cache

        page = urllib2.urlopen(self._search_url).read()
        exp = re.compile(self._search_exp)
        data = exp.findall(page)
        mangas = {}
        for d in data:
            name, url = self._handle_search_data(d)
            mangas[name] = url

        self._search_cache = mangas
        return mangas

    def get_chapters(self, url):
        if self._chapter_cache:
            if url in self._chapter_cache:
                return self._chapter_cache[url]
        else:
            self._chapter_cache = {}

        page = urllib2.urlopen(url)
        page = page.read()
        exp = re.compile(self._chapter_exp)
        data = exp.findall(page)
        chapters = {}
        for d in data:
            cid, chapter_url = self._handle_chapter_data(d, url)
            chapters[cid] = chapter_url
        self._chapter_cache[url] = chapters
        return chapters

    def get_page_urls(self, url):
        if self._page_cache:
            if url in self._page_cache:
                return self._page_cache[url]
        else:
            self._page_cache = {}

        page = urllib2.urlopen(url)
        page = page.read()
        exp = re.compile(self._page_exp)
        data = exp.findall(page)
        pages = {}
        for d in data:
            pid, p = self._handle_page_data(d, url)
            pages[pid] = p

        self._page_cache[url] = pages
        return pages

    def get_chapter_images(self, url):
        imgs = []
        urls = self.get_page_urls(url)
        for page in urls.values():
            img = self.get_image_url(page)
            imgs.append(img)
        return imgs

    def get_image_url(self, url):
        if self._image_cache:
            if url in self._image_cache:
                return self._image_cache(url)
        else:
            self._image_cache = {}

        page = urllib2.urlopen(url)
        page = page.read()
        exp = re.compile(self._image_exp)
        data = exp.findall(page)[0]
        img = self._handle_image_data(data)
        
        self._image_cache[url] = img
        return img

class BleachExile(Page):
    _base_url = "http://manga.bleachexile.com/"
    _search_exp = "<td[^><]*><a href=\"/([^\"]*)\">([^<>]*)</a></td>"
    _search_url = "http://manga.bleachexile.com/series.html"
    _chapter_exp = "<option value=\"([\d]*)\"[^<>]*>Chapter ([^<>]*)</option>"
    _image_exp = "<td colspan=\".\" class=\"page_image\" align=\"center\">.*<img src=\"([^\"]*)\" border=\"0\" alt=\"[^\"]*\"[^<>]* />"
    _page_exp = "<option value=\"([\d]*)\"[^<>]*>Page [^<>]*</option>"

    def _handle_search_data(self, data):
        page, name = data
        url = self._base_url + page
        return (name, url)

    def _handle_image_data(self, data):
        return data

    def _handle_chapter_data(self, data, url):
        counter, cid = data
        counter = int(counter)
        url = url.replace(".html", "")
        url = "%s-chapter-%i.html" % (url, counter)
        return (cid, url)

    def _handle_page_data(self, data, url):
        page = int(data)
        url = url.replace(".html", "")
        url = "%s-page-%i.html" % (url, page)
        return (page, url)

class Job:
    _page = None
    _url = ""
    _dir = ""
    _downloads = None
    _max_downloads = 10
    
    def __init__(self, page, chapter_url, target_dir):
        self._page = page
        self._dir = target_dir
        self._url = chapter_url
        self._downloads = []

        if not path.exists(self._dir):
            os.makedirs(self._dir)

    def run(self):
        page = self._page
        
        os.chdir(self._dir)
        if os.path.exists("DONE"):
            return
        
        urls = page.get_chapter_images(self._url)
        for url in urls:
            self._wait_for_free_slot()
            self._download_file(url)

        # wait until all downloads are finished
        self._max_downloads = 0
        self._wait_for_free_slot()

        f = open("DONE", "w+")
        f.write("%i" % len(urls))
        f.close()

    def _wait_for_free_slot(self):
        while len(self._downloads) > self._max_downloads:
            changed = False
            for d in list(self._downloads):
                # check if process is still running
                if d.poll:
                    changed = True
                    self._downloads.remove(d)
            # don't check more than 5 times per sec
            if not changed:
                time.sleep(0.1)

    def _download_file(self, url):
        cmd = "wget -c -q \"%s\"" % url
        cmd = shlex.split(cmd)
        proc = subprocess.Popen(cmd)
        
        self._downloads.append(proc)
                
class Downloader:
    _name = ""
    _page = None
    _path = ""
    _zipper = None
    _chapters = None

    def __init__(self, page, name, chapters=None):
        self._page = page
        self._name = self.get_manga_name(name)
        self._path = path.join(MANGA_DIR, name)
        self._chapters = chapters

        self._zipper = Zipper(self._path, wait=5)
        self._zipper.daemon = True
        self._zipper.start()

    def run(self):
        mangas = self._page.get_mangas()
        url = mangas[self._name]
        chapters = self._page.get_chapters(url)
        for cid in sorted(chapters):
            if self._chapters\
            and cid not in self._chapters:
                continue
            chapter_dir = path.join(self._path, cid)
            job = Job(self._page, chapters[cid], chapter_dir)
            print "Downloading Chapter %s" % cid
            job.run()
        time.sleep(20)
        self._zipper.join()

    def get_manga_name(self, name):
        names = self._page.search_manga(name)
        if len(names) > 1:
            print "Did you mean..."
            for i, name in enumerate(names, 1):
                print "(%i) %s" % (i, name)
            
            while True:
                print ": ", 
                num = raw_input()
                try:
                    num = int(num)
                except:
                    print "Not a number!"
                    continue
                if num < len(names) and num > 0:
                    return names[num-1]

        return names[0]

def print_help():
    print "%s MANGA [CHAPTERS]" % sys.argv[0]

chapters = None
if len(sys.argv) > 2:
    chapters = sys.argv[2:]
elif len(sys.argv) < 2:
    print_help()
    sys.exit()

page = BleachExile()
downloader = Downloader(page, sys.argv[1], chapters)
downloader.run()
