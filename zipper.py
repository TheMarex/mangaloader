#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import sys
import threading
import subprocess
import os
import os.path as path
import shlex
import time

HOME_DIR = os.environ['HOME']
MANGA_DIR = path.join(HOME_DIR, "Bücher/Mangas/")

class Zipper(threading.Thread):
    _path = ""
    _wait = 0
    _done = True

    def __init__(self, path, done=True, wait=0):
        self._path = path
        self._wait = wait
        self._done = done
        threading.Thread.__init__(self)

    def run(self):
        time.sleep(self._wait)
        print "Checking for new files to zip..."
        chapters = os.listdir(self._path)
        for cid in chapters:
            chapter_dir = path.join(self._path, cid)
            if not path.isdir(chapter_dir):
                continue

            done = path.join(chapter_dir, "DONE") 
            if (self._done and path.exists(done)) or not self._done:
                self.zip_chapter(cid, chapter_dir, done)
    
    def zip_chapter(self, cid, chapter_dir, done):
        chapter_cbz = path.join(self._path, "%s.cbz" % cid)
        if path.exists(chapter_cbz):
            return
       
        files = os.listdir(chapter_dir)

        l = ""
        if self._done:
            f = open(done)
            l = f.read()
            f.close()
            files.remove("DONE")
        else:
            l = "DONE."

        # Check if all files are written to disk. ext4 work-a-round
        if l != "DONE." and int(l) != len(files):
            return
        files = map(lambda x: "\"%s\"" % path.join(chapter_dir, x), files)
        files = sorted(files)
        files = " ".join(files)
        print "Zipping %s..." % cid
        cmd = "zip -j -q \"%s\" %s" % (chapter_cbz, files)
        cmd = shlex.split(cmd)
        subprocess.call(cmd)

if __name__ == "__main__":
    mangas = []
    if len(sys.argv) > 1:
        mangas = sys.argv[1:]
    else:
        mangas = os.listdir(MANGA_DIR)
    
    jobs = []
    for manga in mangas:
        manga_path = path.join(MANGA_DIR, manga)
        zipper = Zipper(manga_path, done=False)
        zipper.daemon = True
        zipper.start()
        jobs.append(zipper)

    for job in jobs:
        job.join()

