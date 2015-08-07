#!/usr/bin/env python
SCULPTEO_SERVER = 'http://www.sculpteo.com'
SCULPTEO_UPLOADFILE = 'upload/file'
SCULPTEO_UPLOAD = 'upload_design/3D'

from uuid import uuid1
import urllib2
import base64
import webbrowser

def post_design(filename, name, lang='en'):
    uuid = uuid1().int

    # post the file as base64 encoded content
    file_string = base64.urlsafe_b64encode(open(filename, 'rb').read())
    post_data = 'file=%s&filename=%s' % (file_string, filename)
    post_url = '%s/%s/%s/?X-Progress-ID=%s' % (SCULPTEO_SERVER, lang, SCULPTEO_UPLOADFILE, uuid)

    print 'POST %s DATA %s' % (post_url, post_data)
    page = urllib2.urlopen(post_url, post_data)
    print post_url, '\n', post_data

    # redirect to upload page to add name, description, etc...
    #webbrowser.open_new
#    print '%s/%s/%s/?X-Progress-ID=%s&name=%s' % (SCULPTEO_SERVER, lang, SCULPTEO_UPLOAD, uuid, name)

def generate_cube(filename):
    f = open(filename, 'wb')
    # vertices
    f.write("v  1 -1 -1\n")
    f.write("v -1 -1 -1\n")
    f.write("v  1  1  1\n")
    f.write("v -1 -1  1\n")
    f.write("v  1 -1  1\n")
    f.write("v -1  1  1\n")
    f.write("v  1  1 -1\n")
    f.write("v -1  1 -1\n")
    # faces
    f.write("f 7 1 2\n")
    f.write("f 7 2 8\n")
    f.write("f 3 6 4\n")
    f.write("f 3 4 5\n")
    f.write("f 7 3 5\n")
    f.write("f 7 5 1\n")
    f.write("f 1 5 4\n")
    f.write("f 1 4 2\n")
    f.write("f 2 4 6\n")
    f.write("f 2 6 8\n")
    f.write("f 3 7 8\n")
    f.write("f 3 8 6\n")
    f.close()

def main():
    print "generate cube"
    generate_cube('example_cube.obj')
    print "post it"
    post_design('example_cube.obj', 'cube')

if __name__ == '__main__':
    main()

