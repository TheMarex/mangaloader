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
    _jobs = None
    _only_done = True
    _stay_alive = False

    def __init__(self, path, jobs, done=True, wait=0):
        self._path = path
        self._jobs = jobs
        self._wait = wait
        self._only_done = done
        threading.Thread.__init__(self)

    def stay_alive(self, flag):
        self._stay_alive = flag

    def add_job(self, job):
        self._jobs.append(job)

    def run(self):
        ttl = 10
        while (len(self._jobs) > 0 and ttl > 0) or self._stay_alive:
            time.sleep(self._wait)
            for cid in list(self._jobs):
                chapter_dir = path.join(self._path, cid)
                if not path.isdir(chapter_dir):
                    print "ERROR: Not a directory %s" % chapter_dir
                    continue

                done = path.join(chapter_dir, "DONE")
                zipped = False
                if (self._only_done and path.exists(done)) or not self._only_done:
                    zipped = self.zip_chapter(cid, chapter_dir, done)

                if zipped:
                    self._jobs.remove(cid)
                    ttl = 10
                else:
                    ttl -= 1

        if len(self._jobs):
            print "ERROR: Could not finish %i jobs: %s" % (len(self._jobs), " ".join(self._jobs))

    def zip_chapter(self, cid, chapter_dir, done):
        chapter_cbz = path.join(self._path, "%s.cbz" % cid)
        if path.exists(chapter_cbz):
            return False
       
        files = os.listdir(chapter_dir)

        l = ""
        if self._only_done:
            f = open(done)
            l = f.read()
            f.close()
            files.remove("DONE")
        else:
            l = "DONE."

        # Check if all files are written to disk. ext4 work-a-round
        if l != "DONE." and int(l) != len(files):
            return False
        files = map(lambda x: "\"%s\"" % path.join(chapter_dir, x), files)
        files = sorted(files)
        files = " ".join(files)
        print "Zipping %s..." % cid
        cmd = "zip -j -q \"%s\" %s" % (chapter_cbz, files)
        cmd = shlex.split(cmd)
        subprocess.call(cmd)

        return True

if __name__ == "__main__":
    mangas = []
    if len(sys.argv) > 1:
        mangas = sys.argv[1:]
    else:
        mangas = os.listdir(MANGA_DIR)
    
    jobs = []
    for manga in mangas:
        manga_path = path.join(MANGA_DIR, manga)
        chaps = os.listdir(manga_path)
        chaps = filter(lambda x: path.isdir(path.join(manga_path, x)), chaps)
        zipper = Zipper(manga_path, chaps, done=False)
        zipper.daemon = True
        zipper.start()
        jobs.append(zipper)

    for job in jobs:
        job.join()

